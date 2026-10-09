import { describe, it, expect } from 'vitest'
import {
  cleanRedirectUrl,
  isValidHttpUrl,
  isExternalOrTargetLink,
  extractUrlFromText
} from '../src/main/services/browser-helper'

describe('Browser Navigation & URL Unwrapping Helper', () => {
  const sampleUserUrl =
    'https://lighthouse.treeiq.biz/blog/i-forced-open-the-locked-door-expecting-the-worst-only-to-find-our-new-maid-asleep-in-my-late-wife-s-bed-with-my-twins-and-their-first-genuine-smile-in-fourteen-months'

  describe('Happy Paths', () => {
    it('unwraps Facebook redirect link (l.facebook.com) to direct target URL', () => {
      const fbUrl = 'https://l.facebook.com/l.php?u=https%3A%2F%2Fbaomoi.com%2Ftin-nong-123.epi&h=AT123XYZ'
      const result = cleanRedirectUrl(fbUrl)
      expect(result).toBe('https://baomoi.com/tin-nong-123.epi')
    })

    it('unwraps Mobile Facebook redirect link (lm.facebook.com)', () => {
      const fbUrl = 'https://lm.facebook.com/l.php?u=https%3A%2F%2Fdantri.com.vn%2Fxa-hoi%2Fbai-viet.htm&h=ABC'
      const result = cleanRedirectUrl(fbUrl)
      expect(result).toBe('https://dantri.com.vn/xa-hoi/bai-viet.htm')
    })

    it('unwraps exact user treeiq story URL when wrapped in Facebook redirect shim', () => {
      const encodedTarget = encodeURIComponent(sampleUserUrl)
      const fbUrl = `https://l.facebook.com/l.php?u=${encodedTarget}&h=AT999ZZZ`
      const result = cleanRedirectUrl(fbUrl)
      expect(result).toBe(sampleUserUrl)
    })

    it('unwraps Facebook warning interstitial redirect (facebook.com/flx/warn)', () => {
      const fbUrl = 'https://www.facebook.com/flx/warn/?u=https%3A%2F%2Fvnexpress.net%2Fthoi-su'
      const result = cleanRedirectUrl(fbUrl)
      expect(result).toBe('https://vnexpress.net/thoi-su')
    })

    it('unwraps Instagram linkshim redirect (l.instagram.com)', () => {
      const igUrl = 'https://l.instagram.com/?u=https%3A%2F%2Fkenh14.vn%2Fstar.chn&e=AT456'
      const result = cleanRedirectUrl(igUrl)
      expect(result).toBe('https://kenh14.vn/star.chn')
    })

    it('unwraps Google redirect URL (google.com/url?q=...)', () => {
      const gUrl = 'https://www.google.com/url?q=https%3A%2F%2Ftuoitre.vn%2Fkinh-doanh.htm&sa=U'
      const result = cleanRedirectUrl(gUrl)
      expect(result).toBe('https://tuoitre.vn/kinh-doanh.htm')
    })

    it('unwraps YouTube redirect URL (youtube.com/redirect?q=...)', () => {
      const ytUrl = 'https://www.youtube.com/redirect?q=https%3A%2F%2Fthanhnien.vn%2F&event=video_description'
      const result = cleanRedirectUrl(ytUrl)
      expect(result).toBe('https://thanhnien.vn/')
    })

    it('leaves standard news and content URLs unmodified', () => {
      const directUrl = 'https://baomoi.com/tin-tuc-trong-ngay.epi'
      expect(cleanRedirectUrl(directUrl)).toBe(directUrl)
      expect(cleanRedirectUrl(sampleUserUrl)).toBe(sampleUserUrl)
    })

    it('leaves standard Facebook post/reel URLs unmodified', () => {
      const reelUrl = 'https://www.facebook.com/reel/1234567890'
      expect(cleanRedirectUrl(reelUrl)).toBe(reelUrl)
    })
  })

  describe('Comment Link Extraction (extractUrlFromText)', () => {
    it('extracts exact user story link from raw comment string', () => {
      const comment = `Xem bài viết tại: ${sampleUserUrl}`
      const extracted = extractUrlFromText(comment)
      expect(extracted).toBe(sampleUserUrl)
    })

    it('removes trailing punctuation (dot, comma, bracket) from comment links', () => {
      const commentWithDot = `Đọc truyện hay tại ${sampleUserUrl}. Hay lắm nè!`
      expect(extractUrlFromText(commentWithDot)).toBe(sampleUserUrl)

      const commentWithParen = `(Link đọc: ${sampleUserUrl})`
      expect(extractUrlFromText(commentWithParen)).toBe(sampleUserUrl)
    })

    it('unwraps Facebook redirect link embedded inside a comment sentence', () => {
      const comment = `Link đây nhé: https://l.facebook.com/l.php?u=https%3A%2F%2Fbaomoi.com%2Ftin-tuc.htm&h=test`
      const extracted = extractUrlFromText(comment)
      expect(extracted).toBe('https://baomoi.com/tin-tuc.htm')
    })

    it('returns null when text contains no URLs', () => {
      expect(extractUrlFromText('Bình luận không có link gì cả')).toBeNull()
      expect(extractUrlFromText('')).toBeNull()
    })
  })

  describe('External & Target Link Detection (isExternalOrTargetLink)', () => {
    it('identifies external blog/story links as valid target links', () => {
      expect(isExternalOrTargetLink(sampleUserUrl)).toBe(true)
      expect(isExternalOrTargetLink('https://dantri.com.vn/suc-manh-so.htm')).toBe(true)
    })

    it('identifies Facebook / Instagram redirect shims as target links', () => {
      expect(isExternalOrTargetLink('https://l.facebook.com/l.php?u=...')).toBe(true)
      expect(isExternalOrTargetLink('https://lm.facebook.com/l.php?u=...')).toBe(true)
      expect(isExternalOrTargetLink('https://l.instagram.com/?u=...')).toBe(true)
    })

    it('identifies explicit reel or watch links as target links', () => {
      expect(isExternalOrTargetLink('https://www.facebook.com/reel/123456')).toBe(true)
      expect(isExternalOrTargetLink('https://facebook.com/watch?v=789')).toBe(true)
    })

    it('rejects internal facebook chrome, empty or javascript links', () => {
      expect(isExternalOrTargetLink('#')).toBe(false)
      expect(isExternalOrTargetLink('javascript:void(0)')).toBe(false)
      expect(isExternalOrTargetLink('https://www.facebook.com/friends')).toBe(false)
      expect(isExternalOrTargetLink('')).toBe(false)
    })
  })

  describe('Edge Cases', () => {
    it('handles double-encoded redirect URLs gracefully', () => {
      const doubleEncoded = 'https://l.facebook.com/l.php?u=https%253A%252F%252Fbaomoi.com%252Ftin-tuc&h=xyz'
      const result = cleanRedirectUrl(doubleEncoded)
      expect(result).toBe('https://baomoi.com/tin-tuc')
    })

    it('returns empty string for empty, null, or undefined input', () => {
      expect(cleanRedirectUrl('')).toBe('')
      // @ts-ignore
      expect(cleanRedirectUrl(null)).toBe('')
      // @ts-ignore
      expect(cleanRedirectUrl(undefined)).toBe('')
      expect(cleanRedirectUrl('   ')).toBe('')
    })

    it('handles internal Facebook URL without u parameter without crashing', () => {
      const fbUrl = 'https://l.facebook.com/l.php'
      expect(cleanRedirectUrl(fbUrl)).toBe(fbUrl)
    })

    it('handles about:blank and special browser schemes', () => {
      expect(cleanRedirectUrl('about:blank')).toBe('about:blank')
    })
  })

  describe('Error Handling & Validation', () => {
    it('returns original input when URL parsing fails on malformed strings', () => {
      const malformed = 'not-a-valid-url://??'
      expect(cleanRedirectUrl(malformed)).toBe(malformed)
    })

    it('rejects unsafe schemes in u parameter such as javascript: or data:', () => {
      const unsafe = 'https://l.facebook.com/l.php?u=javascript%3Aalert(1)'
      expect(cleanRedirectUrl(unsafe)).toBe(unsafe)
    })

    it('validates http and https URLs correctly with isValidHttpUrl', () => {
      expect(isValidHttpUrl('https://baomoi.com')).toBe(true)
      expect(isValidHttpUrl('http://localhost:3000')).toBe(true)
      expect(isValidHttpUrl('ftp://example.com')).toBe(false)
      expect(isValidHttpUrl('javascript:void(0)')).toBe(false)
      expect(isValidHttpUrl('')).toBe(false)
      // @ts-ignore
      expect(isValidHttpUrl(null)).toBe(false)
    })
  })
})
