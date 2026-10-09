import { describe, it, expect, vi } from 'vitest'
import {
  cleanCaptionText,
  mergeContent,
  createContentForReel,
  extractBaoGocFromText,
  extractBaoGoc,
  shouldAutoMergeContent,
  autoMergeIfEligible,
  resolveMediaProtocolPath,
  ContentGenerator
} from '../src/main/services/content-generator'


describe('ContentGenerator Service', () => {
  // ================= 1. HAPPY PATHS =================
  describe('Happy Paths', () => {
    it('cleans reel caption by stripping existing http/https links, trailing link labels and trimming whitespace', () => {
      const raw = 'Cực sốc với tin tức mới nhất hôm nay https://bit.ly/123 Xem chi tiết tại: https://vnexpress.net/bai-bao-123 | Facebook'
      const cleaned = cleanCaptionText(raw)
      expect(cleaned).toBe('Cực sốc với tin tức mới nhất hôm nay')
      expect(cleaned).not.toContain('http')
      expect(cleaned).not.toContain('Facebook')
    })

    it('merges clean caption and new article link (bao_moi) into complete content', () => {
      const caption = 'Vụ việc kịch tính vừa xảy ra tại Hà Nội khiến dư luận xôn xao https://fb.watch/xyz'
      const baoMoi = 'https://baomoi.com/vu-viec-nong-123.epi'
      const result = mergeContent(caption, baoMoi)

      expect(result).toBe(
        'Vụ việc kịch tính vừa xảy ra tại Hà Nội khiến dư luận xôn xao\n\nhttps://baomoi.com/vu-viec-nong-123.epi'
      )
    })

    it('createContentForReel follows rule: content = caption reels (bài gốc, đã loại bỏ link đính kèm) + link báo mới', async () => {
      // Mock extractReelCaption
      const spy = vi.spyOn(ContentGenerator, 'extractReelCaption').mockResolvedValue(
        'Nội dung phim kịch tính phần 4 https://linkphim.com/xem Nguồn: https://fb.watch/123'
      )

      const res = await createContentForReel(
        'https://www.facebook.com/reel/123456789',
        'https://baomoi.com/phim-hay-123.epi',
        ''
      )

      expect(spy).toHaveBeenCalledWith('https://www.facebook.com/reel/123456789')
      expect(res.cleanCaption).toBe('Nội dung phim kịch tính phần 4')
      expect(res.content).toBe(
        'Nội dung phim kịch tính phần 4\n\nhttps://baomoi.com/phim-hay-123.epi'
      )
      expect(res.content).not.toContain('https://linkphim.com')
      expect(res.content).not.toContain('https://fb.watch')

      spy.mockRestore()
    })

    it('extracts external original news link (bao_goc) from caption text or author comment', () => {
      const text = 'Nguồn bài viết gốc: https://tuoitre.vn/nong-vu-an-dac-biet-12345.htm Theo dõi thêm nhé'
      const link = extractBaoGocFromText(text)
      expect(link).toBe('https://tuoitre.vn/nong-vu-an-dac-biet-12345.htm')
    })

    it('decodes facebook redirect link (l.facebook.com) to find the original news URL', () => {
      const text = 'Xem bài báo tại: https://l.facebook.com/l.php?u=https%3A%2F%2Fdantri.com.vn%2Fxa-hoi%2Ftin-tuc.htm&h=AT123'
      const link = extractBaoGocFromText(text)
      expect(link).toBe('https://dantri.com.vn/xa-hoi/tin-tuc.htm')
    })

    it('determines if content should be automatically merged when bao_moi is present and not yet merged', () => {
      expect(shouldAutoMergeContent('Nội dung phim', 'https://baomoi.com/tin-tuc.epi')).toBe(true)
      expect(shouldAutoMergeContent('', 'https://baomoi.com/tin-tuc.epi')).toBe(true)
      expect(shouldAutoMergeContent(null, 'https://baomoi.com/tin-tuc.epi')).toBe(true)
    })

    it('autoMergeIfEligible merges caption and bao_moi automatically', () => {
      const merged = autoMergeIfEligible('Nội dung phim hay', 'https://baomoi.com/phim.epi')
      expect(merged).toBe('Nội dung phim hay\n\nhttps://baomoi.com/phim.epi')
    })

    it('resolves media-file protocol URLs containing query parameter path', () => {
      const localWinPath = 'C:\\Users\\Trant\\Videos\\sample_1.mp4'
      const protocolUrl = `media-file://video?path=${encodeURIComponent(localWinPath)}`
      const resolved = resolveMediaProtocolPath(protocolUrl)
      expect(resolved.replace(/\\/g, '/')).toBe('C:/Users/Trant/Videos/sample_1.mp4')
    })

    it('recovers stripped colon on Windows drive letter in media-file pathname', () => {
      const strippedUrl = 'media-file://c/Users/Trant/Videos/1.mp4'
      const resolved = resolveMediaProtocolPath(strippedUrl)
      expect(resolved.replace(/\\/g, '/').toLowerCase()).toBe('c:/users/trant/videos/1.mp4')
    })

    it('autoMergeAllEligible scans mock database and merges eligible rows automatically', async () => {
      const updatedFields: Record<string, any> = {}
      const mockDb = {
        getAllVideos: () => [
          { stt: '1', bao_moi: 'https://baomoi.com/tin-moi', content: 'Tóm tắt bài báo rất hay và đầy đủ chi tiết' },
          { stt: '2', bao_moi: 'https://baomoi.com/da-ghep', content: 'Nội dung rất hay và hấp dẫn\n\nhttps://baomoi.com/da-ghep' },
          { stt: '3', bao_moi: '', content: 'Không có báo mới' }
        ],
        updateSingleField: (stt: string, field: string, val: any) => {
          updatedFields[`${stt}_${field}`] = val
        }
      }

      const res = await ContentGenerator.autoMergeAllEligible(mockDb)
      expect(res.updatedCount).toBe(1)
      expect(updatedFields['1_content']).toBe('Tóm tắt bài báo rất hay và đầy đủ chi tiết\n\nhttps://baomoi.com/tin-moi')
      expect(updatedFields['2_content']).toBeUndefined()
    })
  })


  // ================= 2. EDGE CASES =================
  describe('Edge Cases', () => {
    it('returns empty string when caption is empty or null', () => {
      expect(cleanCaptionText('')).toBe('')
      expect(cleanCaptionText(null as any)).toBe('')
      expect(cleanCaptionText(undefined as any)).toBe('')
    })

    it('handles caption containing only URLs', () => {
      const raw = 'https://vnexpress.net https://dantri.com.vn'
      expect(cleanCaptionText(raw)).toBe('')
      expect(mergeContent(raw, 'https://newsite.com')).toBe('https://newsite.com')
    })

    it('handles missing bao_moi URL by returning only clean caption', () => {
      const raw = 'Nội dung thú vị không có link báo https://test.com'
      expect(mergeContent(raw, '')).toBe('Nội dung thú vị không có link báo')
      expect(mergeContent(raw, undefined as any)).toBe('Nội dung thú vị không có link báo')
    })

    it('shouldAutoMergeContent returns false if bao_moi is empty or already merged', () => {
      expect(shouldAutoMergeContent('Nội dung bài viết', '')).toBe(false)
      expect(shouldAutoMergeContent('Nội dung bài viết', '   ')).toBe(false)
      expect(shouldAutoMergeContent('Nội dung bài viết\n\nhttps://baomoi.com/123', 'https://baomoi.com/123')).toBe(false)
    })

    it('autoMergeIfEligible returns existing content unchanged when already merged', () => {
      const existing = 'Nội dung bài viết\n\nhttps://baomoi.com/123'
      expect(autoMergeIfEligible(existing, 'https://baomoi.com/123')).toBe(existing)
    })

    it('ignores internal facebook/instagram links when extracting bao_goc', () => {
      const text = 'Xem reel khác tại https://www.facebook.com/reel/99999999 hoặc https://instagram.com/p/123'
      const link = extractBaoGocFromText(text)
      expect(link).toBe('')
    })

    it('prioritizes external news article over facebook links in author comment', () => {
      const text = 'Page: https://facebook.com/mypage - Báo gốc: https://plo.vn/thoi-su/tin-moi-123.html'
      const link = extractBaoGocFromText(text)
      expect(link).toBe('https://plo.vn/thoi-su/tin-moi-123.html')
    })

    it('createContentForReel replaces old bao_moi link without duplicating URLs', async () => {
      const existing = 'Kịch bản tổng tài hấp dẫn\n\nhttps://old-news.com/123'
      const res = await createContentForReel('', 'https://new-news.com/456', existing)
      expect(res.content).toBe('Kịch bản tổng tài hấp dẫn\n\nhttps://new-news.com/456')
      expect(res.content).not.toContain('https://old-news.com/123')
    })

    it('createContentForReel ignores existing content if it only contains an old URL and extracts from reel', async () => {
      const spy = vi.spyOn(ContentGenerator, 'extractReelCaption').mockResolvedValue(
        'Phim kiếm hiệp siêu phẩm mới ra mắt'
      )

      const res = await createContentForReel(
        'https://fb.com/reel/111',
        'https://baomoi.com/kiem-hiep',
        'https://some-old-url.com' // only an old URL, no text!
      )

      expect(res.content).toBe('Phim kiếm hiệp siêu phẩm mới ra mắt\n\nhttps://baomoi.com/kiem-hiep')
      spy.mockRestore()
    })
  })

  // ================= 3. ERROR HANDLING =================
  describe('Error Handling', () => {
    it('safely extracts bao_goc from invalid or empty URL', async () => {
      const res = await extractBaoGoc('')
      expect(res).toBe('')
    })

    it('handles malformed URL strings without crashing', () => {
      expect(extractBaoGocFromText('some text with invalid http:// incomplete')).toBe('')
      expect(extractBaoGocFromText('not a url at all')).toBe('')
    })

    it('handles malformed media-file URLs gracefully in resolveMediaProtocolPath', () => {
      expect(resolveMediaProtocolPath('')).toBe('')
      expect(resolveMediaProtocolPath('not-a-url')).toBe('not-a-url')
    })
  })
})

