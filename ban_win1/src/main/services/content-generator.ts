import path from 'path'
import axios from 'axios'
import { FacebookDownloader } from './fb-downloader'

export function cleanCaptionText(text?: string | null): string {
  if (!text) return ''
  let cleaned = text
    .replace(/https?:\/\/[^\s"'<>]+/gi, '')
    .replace(/\s*\|\s*Facebook/gi, '')
    .replace(/\s*-\s*Facebook/gi, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n\s*\n\s*\n+/g, '\n\n')
    .trim()

  // Remove trailing link labels left behind after stripping URLs (e.g. "Xem chi tiết tại:", "Nguồn:", "Link:")
  cleaned = cleaned
    .replace(
      /(\b(Link|Nguồn|Nguồn tin|Link bài|Link gốc)\s*[:：\-]*\s*|\b(Xem thêm|Xem chi tiết|Chi tiết)\s*(tại)?\s*[:：\-]+\s*)$/i,
      ''
    )
    .trim()

  return cleaned
}

export function mergeContent(caption?: string | null, baoMoiUrl?: string | null): string {
  const clean = cleanCaptionText(caption)
  const url = (baoMoiUrl || '').trim()
  if (clean && url) {
    return `${clean}\n\n${url}`
  }
  return clean || url || ''
}

export function shouldAutoMergeContent(caption?: string | null, baoMoiUrl?: string | null): boolean {
  const url = (baoMoiUrl || '').trim()
  if (!url) return false
  const current = (caption || '').trim()
  if (!current) return true
  return !current.includes(url)
}

export function autoMergeIfEligible(caption?: string | null, baoMoiUrl?: string | null): string {
  const url = (baoMoiUrl || '').trim()
  if (!url) return caption || ''
  if (!shouldAutoMergeContent(caption, url)) {
    return caption || ''
  }
  return mergeContent(caption, url)
}

export function resolveMediaProtocolPath(requestUrl: string): string {
  if (!requestUrl) return ''
  try {
    const url = new URL(requestUrl)
    const paramPath = url.searchParams.get('path')
    if (paramPath) {
      return path.normalize(paramPath)
    }

    let raw = decodeURIComponent(requestUrl.replace(/^media-file:\/\//, ''))
    if (/^[a-zA-Z]\//.test(raw)) {
      raw = raw[0] + ':/' + raw.slice(2)
    } else if (/^\/[a-zA-Z]:/.test(raw)) {
      raw = raw.slice(1)
    }
    return path.normalize(raw)
  } catch {
    return requestUrl
  }
}

export function extractBaoGocFromText(text?: string | null): string {
  if (!text) return ''
  const urlMatches = text.match(/https?:\/\/[^\s"'<>]+/gi) || []
  for (const rawUrl of urlMatches) {
    let candidate = rawUrl.trim().replace(/[.,;:)\]]+$/, '')
    // Decode Facebook redirect links
    if (candidate.includes('l.facebook.com/l.php') || candidate.includes('lm.facebook.com/l.php')) {
      try {
        const uObj = new URL(candidate)
        const realU = uObj.searchParams.get('u')
        if (realU) {
          candidate = decodeURIComponent(realU)
        }
      } catch { }
    }

    // Ignore internal Facebook and Instagram links
    const lower = candidate.toLowerCase()
    if (
      lower.includes('facebook.com') ||
      lower.includes('fb.watch') ||
      lower.includes('fb.me') ||
      lower.includes('instagram.com') ||
      lower.includes('cdn.net') ||
      lower.includes('fbcdn.net')
    ) {
      continue
    }

    // If valid http/https url found, return it
    if (/^https?:\/\/[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+/.test(candidate)) {
      return candidate
    }
  }
  return ''
}

export async function extractBaoGoc(reelUrl: string, htmlContent?: string): Promise<string> {
  const cleanUrl = (reelUrl || '').trim()
  if (!cleanUrl) return ''

  // 1. Try from passed HTML or fetch HTML directly
  let html = htmlContent || ''
  if (!html) {
    try {
      const resp = await axios.get(cleanUrl, {
        headers: {
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        },
        timeout: 10000
      })
      if (typeof resp.data === 'string') {
        html = resp.data
      }
    } catch { }
  }

  if (html) {
    // Check og:description or title
    const ogMatch = html.match(/property=["']og:description["']\s+content=["']([^"']+)["']/i)
    if (ogMatch) {
      const found = extractBaoGocFromText(ogMatch[1])
      if (found) return found
    }

    // Check comments / text blocks in HTML
    const foundFromHtml = extractBaoGocFromText(html)
    if (foundFromHtml) return foundFromHtml
  }

  // 2. Try yt-dlp metadata
  try {
    const meta = await FacebookDownloader.getMetadata(cleanUrl)
    if (meta) {
      const foundFromDesc = extractBaoGocFromText(meta.description || meta.title)
      if (foundFromDesc) return foundFromDesc
    }
  } catch { }

  return ''
}

export async function createContentForReel(
  baiGocUrl?: string | null,
  baoMoiUrl?: string | null,
  existingContent?: string | null,
  forceReExtract = false
): Promise<{ content: string; cleanCaption: string; baoMoi: string }> {
  const url = (baoMoiUrl || '').trim()
  const bg = (baiGocUrl || '').trim()

  let rawCaption = ''

  // 1. If not forcing re-extract, check if existingContent has real caption text (>= 25 chars without URLs)
  if (!forceReExtract && existingContent) {
    const cleanExisting = cleanCaptionText(existingContent)
    if (cleanExisting && cleanExisting.length >= 25) {
      rawCaption = cleanExisting
    }
  }

  // 2. If no caption yet and we have bai_goc, extract directly from Facebook Reel
  if (!rawCaption && bg) {
    try {
      rawCaption = await ContentGenerator.extractReelCaption(bg)
    } catch (e) {
      console.warn('[createContentForReel] Failed to extract reel caption:', e)
    }
  }

  // 3. Fallback: if still empty, use whatever cleanExisting text is present
  if (!rawCaption && existingContent) {
    rawCaption = cleanCaptionText(existingContent)
  }

  // 4. Loại bỏ mọi link đính kèm trong caption reels
  const cleanCaption = cleanCaptionText(rawCaption)

  // 5. Quy tắc chuẩn: content = caption reels(bài gốc, đã loại bỏ link đính kèm) + link báo mới
  let finalContent = ''
  if (cleanCaption && url) {
    finalContent = `${cleanCaption}\n\n${url}`
  } else {
    finalContent = cleanCaption || url || ''
  }

  return {
    content: finalContent,
    cleanCaption,
    baoMoi: url
  }
}

export class ContentGenerator {
  public static cleanCaptionText = cleanCaptionText
  public static mergeContent = mergeContent
  public static createContentForReel = createContentForReel
  public static shouldAutoMergeContent = shouldAutoMergeContent
  public static autoMergeIfEligible = autoMergeIfEligible
  public static resolveMediaProtocolPath = resolveMediaProtocolPath
  public static extractBaoGocFromText = extractBaoGocFromText
  public static extractBaoGoc = extractBaoGoc

  public static async extractReelCaption(reelUrl: string): Promise<string> {
    const cleanUrl = (reelUrl || '').trim()
    if (!cleanUrl) return ''

    // 1. Try FacebookDownloader (yt-dlp + HTML scraping)
    try {
      const meta = await FacebookDownloader.getMetadata(cleanUrl)
      if (meta) {
        const desc = (meta.description || meta.title || '').trim()
        if (desc) return desc
      }
    } catch { }

    // 2. Direct HTTP scrape fallback
    try {
      const resp = await axios.get(cleanUrl, {
        headers: {
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        timeout: 8000
      })
      const html = typeof resp.data === 'string' ? resp.data : ''
      if (html) {
        const mOg =
          html.match(/property=["']og:description["']\s+content=["']([^"']+)["']/i) ||
          html.match(/content=["']([^"']+)["']\s+property=["']og:description["']/i)
        if (mOg && mOg[1]) {
          return mOg[1].replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"').trim()
        }
        const mTitle = html.match(/<title>(.*?)<\/title>/i)
        if (mTitle && mTitle[1]) {
          return mTitle[1].replace(/\s*\|\s*Facebook/gi, '').replace(/\s*-\s*Facebook/gi, '').trim()
        }
      }
    } catch { }

    return ''
  }

  public static async generateWithDeepSeek(
    apiKey: string,
    prompt: string,
    content: string
  ): Promise<string> {
    if (!apiKey) {
      throw new Error('Chưa cấu hình DeepSeek API Key trong Cài đặt.')
    }

    const response = await axios.post(
      'https://api.deepseek.com/chat/completions',
      {
        model: 'deepseek-chat',
        messages: [
          {
            role: 'system',
            content:
              'Bạn là một chuyên gia sáng tạo nội dung mạng xã hội, viết tóm tắt ngắn gọn, thu hút, chuẩn SEO tiếng Việt.'
          },
          {
            role: 'user',
            content: `${prompt}\n\nNội dung cần xử lý:\n${content}`
          }
        ],
        stream: false
      },
      {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey.trim()}`
        },
        timeout: 60000
      }
    )

    if (response.data?.choices?.[0]?.message?.content) {
      return response.data.choices[0].message.content.trim()
    }
    return ''
  }

  public static async batchMergeContent(db: any): Promise<{ updatedCount: number }> {
    const videos = db.getAllVideos()
    let updatedCount = 0

    for (const item of videos) {
      const stt = item.stt
      const baoMoi = (item.bao_moi || '').trim()
      const baiGoc = (item.bai_goc || '').trim()
      let currentContent = (item.content || '').trim()
      let currentBaoGoc = (item.bao_goc || '').trim()
      let modified = false

      // 1. If bao_goc is missing and baiGoc exists, attempt to extract bao_goc
      if (!currentBaoGoc && baiGoc) {
        try {
          const bg = await extractBaoGoc(baiGoc)
          if (bg) {
            db.updateSingleField(stt, 'bao_goc', bg)
            currentBaoGoc = bg
            modified = true
          }
        } catch { }
      }

      // 2. If baoMoi exists, create content = caption reels(bài gốc, đã loại bỏ link đính kèm) + link báo mới
      if (baoMoi) {
        const res = await createContentForReel(baiGoc, baoMoi, currentContent)
        if (res.content && res.content !== currentContent) {
          db.updateSingleField(stt, 'content', res.content)
          const hasVideo = Boolean((item.link_video || '').trim())
          const postStatus = hasVideo ? 'hoàn thành' : 'chưa hoàn thành'
          db.updateSingleField(stt, 'trang_thai_dang_bai', postStatus)
          modified = true
        }
      }

      if (modified) {
        updatedCount++
      }
    }

    return { updatedCount }
  }

  public static async autoMergeAllEligible(db: any): Promise<{ updatedCount: number }> {
    const videos = db.getAllVideos ? db.getAllVideos() : []
    let updatedCount = 0

    for (const item of videos) {
      const stt = item.stt
      const baoMoi = (item.bao_moi || '').trim()
      const baiGoc = (item.bai_goc || '').trim()
      const currentContent = (item.content || '').trim()

      if (baoMoi) {
        const cleanCurrent = cleanCaptionText(currentContent)
        // If content already contains baoMoi AND has substantial reel caption, skip
        if (currentContent.includes(baoMoi) && cleanCurrent.length >= 25) {
          continue
        }

        const res = await createContentForReel(baiGoc, baoMoi, currentContent)
        if (res.content && res.content !== currentContent) {
          if (db.updateSingleField) {
            db.updateSingleField(stt, 'content', res.content)
            const hasVideo = Boolean((item.link_video || '').trim())
            const postStatus = hasVideo ? 'hoàn thành' : 'chưa hoàn thành'
            db.updateSingleField(stt, 'trang_thai_dang_bai', postStatus)
          }
          updatedCount++
        }
      }
    }

    return { updatedCount }
  }
}

