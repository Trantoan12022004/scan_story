import { spawn } from 'child_process'
import axios from 'axios'
import { getBinaryPath } from './binary-resolver'

export interface PostStats {
  views: number
  likes: number
  comments: number
  scanned_at: string
}

/**
 * Decodes decimal, hexadecimal, and named HTML entities into plain unicode text
 */
export function decodeHtmlEntities(str: string): string {
  if (!str || typeof str !== 'string') return ''
  return str
    .replace(/&#(\d+);/g, (_, dec) => String.fromCharCode(Number(dec)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&middot;/g, '·')
    .replace(/&nbsp;/g, ' ')
}

/**
 * Parses numbers with thousand separators and suffixes (e.g., "1.5K", "4,4K", "2.4M", "1,250", "15.000")
 */
export function parseStatNumber(val: string | number | null | undefined): number {
  if (val === null || val === undefined) return 0
  if (typeof val === 'number') {
    return isNaN(val) ? 0 : Math.round(val)
  }

  const clean = String(val).trim().toUpperCase()
  if (!clean || clean === '0') return 0

  // Match leading digits, dots, commas, and optional suffix
  const match = clean.match(/^([\d.,]+)\s*([KMB])?/)
  if (!match) return 0

  let numStr = match[1]
  const suffix = match[2] || (clean.includes('B') ? 'B' : clean.includes('M') ? 'M' : clean.includes('K') ? 'K' : '')

  if (suffix === 'B') {
    const n = parseFloat(numStr.replace(/,/g, '.'))
    return isNaN(n) ? 0 : Math.round(n * 1000000000)
  }
  if (suffix === 'M') {
    const n = parseFloat(numStr.replace(/,/g, '.'))
    return isNaN(n) ? 0 : Math.round(n * 1000000)
  }
  if (suffix === 'K') {
    // European / Vietnamese decimal comma: "4,4K" -> 4400
    const n = parseFloat(numStr.replace(/,/g, '.'))
    return isNaN(n) ? 0 : Math.round(n * 1000)
  }

  // Vietnamese / European dot thousand separator: e.g. "15.000" or "1.500.000"
  if (/^\d{1,3}(\.\d{3})+$/.test(numStr)) {
    numStr = numStr.replace(/\./g, '')
  } else if (/^\d{1,3}(,\d{3})+$/.test(numStr)) {
    numStr = numStr.replace(/,/g, '')
  } else if (/^\d+,\d{1,2}$/.test(numStr)) {
    // Single decimal comma: e.g. "4,4"
    numStr = numStr.replace(/,/g, '.')
  } else {
    numStr = numStr.replace(/,/g, '')
  }

  const parsed = parseFloat(numStr)
  return isNaN(parsed) ? 0 : Math.round(parsed)
}

/**
 * Formats a raw number into human-readable representation:
 * 850 -> "850", 1500 -> "1.5K", 25400 -> "25.4K", 1200000 -> "1.2M"
 */
export function formatStatNumber(num: number | null | undefined): string {
  if (!num || isNaN(num) || num <= 0) return '0'

  if (num < 1000) {
    return num.toString()
  }
  if (num < 1000000) {
    const k = (num / 1000).toFixed(1).replace(/\.0$/, '')
    return `${k}K`
  }
  if (num < 1000000000) {
    const m = (num / 1000000).toFixed(1).replace(/\.0$/, '')
    return `${m}M`
  }
  const b = (num / 1000000000).toFixed(1).replace(/\.0$/, '')
  return `${b}B`
}

/**
 * Extracts view, like, and comment metrics from a title, description, or meta string.
 * Common format: "4.4K views · 53 reactions | Story title..." or "12 reactions | ..."
 */
export function parseMetricsFromText(text: string | null | undefined): {
  views: number
  likes: number
  comments: number
} {
  if (!text || typeof text !== 'string') {
    return { views: 0, likes: 0, comments: 0 }
  }

  // Decode common HTML entities
  const decoded = decodeHtmlEntities(text)

  // Facebook & social media often put stats in a prefix before '|' or '\n'
  let statsPrefix = decoded
  if (decoded.includes('|')) {
    statsPrefix = decoded.split('|')[0]
  } else if (decoded.includes('\n')) {
    statsPrefix = decoded.split('\n')[0]
  }

  let views = 0
  let likes = 0
  let comments = 0

  // 1. Views
  const viewMatch =
    statsPrefix.match(/([\d.,]+\s*[kKmMbB]?)\s*(?:views?|lượt xem|lượt phát|view)/i) ||
    statsPrefix.match(/(?:views?|lượt xem|lượt phát)\s*[:=·-]?\s*([\d.,]+\s*[kKmMbB]?)/i) ||
    decoded.match(/([\d.,]+\s*[kKmMbB]?)\s*(?:views?|lượt xem|lượt phát)\b/i)
  if (viewMatch && viewMatch[1]) {
    views = parseStatNumber(viewMatch[1])
  }

  // 2. Likes / Reactions
  const likeMatch =
    statsPrefix.match(/([\d.,]+\s*[kKmMbB]?)\s*(?:reactions?|cảm xúc|lượt thích|likes?|người thích|thích)/i) ||
    statsPrefix.match(/(?:reactions?|cảm xúc|lượt thích|likes?)\s*[:=·-]?\s*([\d.,]+\s*[kKmMbB]?)/i) ||
    decoded.match(/([\d.,]+\s*[kKmMbB]?)\s*(?:reactions?|cảm xúc|lượt thích|likes?)\b/i)
  if (likeMatch && likeMatch[1]) {
    likes = parseStatNumber(likeMatch[1])
  }

  // 3. Comments
  const cmtMatch =
    statsPrefix.match(/([\d.,]+\s*[kKmMbB]?)\s*(?:comments?|bình luận|comment)/i) ||
    statsPrefix.match(/(?:comments?|bình luận)\s*[:=·-]?\s*([\d.,]+\s*[kKmMbB]?)/i) ||
    decoded.match(/([\d.,]+\s*[kKmMbB]?)\s*(?:comments?|bình luận)\b/i)
  if (cmtMatch && cmtMatch[1]) {
    comments = parseStatNumber(cmtMatch[1])
  }

  return { views, likes, comments }
}

/**
 * Scans HTML content for Schema.org JSON-LD, Facebook OpenGraph/Twitter meta tags,
 * GraphQL/Relay caches, and textual patterns
 */
export function extractStatsFromHtml(html: string): { views: number; likes: number; comments: number } {
  let views = 0
  let likes = 0
  let comments = 0

  if (!html || typeof html !== 'string') {
    return { views, likes, comments }
  }

  // 1. Check meta tags (twitter:title, og:title, twitter:image:alt, description, etc.)
  const metaRegex = /<meta\s+[^>]*?(?:name|property)=["']([^"']+)["'][^>]*?content=["']([^"']*)["'][^>]*>/gi
  let metaMatch: RegExpExecArray | null
  while ((metaMatch = metaRegex.exec(html)) !== null) {
    const prop = (metaMatch[1] || '').toLowerCase()
    const content = metaMatch[2] || ''
    if (
      prop.includes('title') ||
      prop.includes('description') ||
      prop.includes('image:alt')
    ) {
      const fromMeta = parseMetricsFromText(content)
      views = Math.max(views, fromMeta.views)
      likes = Math.max(likes, fromMeta.likes)
      comments = Math.max(comments, fromMeta.comments)
    }
  }

  // Also check <title> tag
  const titleTagMatch = html.match(/<title[^>]*>([^<]*)<\/title>/i)
  if (titleTagMatch && titleTagMatch[1]) {
    const fromTitle = parseMetricsFromText(titleTagMatch[1])
    views = Math.max(views, fromTitle.views)
    likes = Math.max(likes, fromTitle.likes)
    comments = Math.max(comments, fromTitle.comments)
  }

  // 2. Check Schema.org JSON-LD scripts
  const jsonLdRegex = /<script\s+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi
  let ldMatch: RegExpExecArray | null
  while ((ldMatch = jsonLdRegex.exec(html)) !== null) {
    try {
      const data = JSON.parse(ldMatch[1].trim())
      const items = Array.isArray(data) ? data : [data]
      for (const item of items) {
        if (item.interactionStatistic && Array.isArray(item.interactionStatistic)) {
          for (const stat of item.interactionStatistic) {
            const typeStr = JSON.stringify(stat.interactionType || '').toLowerCase()
            const count = parseStatNumber(stat.userInteractionCount)
            if (typeStr.includes('watch') || typeStr.includes('view')) {
              views = Math.max(views, count)
            } else if (typeStr.includes('like')) {
              likes = Math.max(likes, count)
            } else if (typeStr.includes('comment')) {
              comments = Math.max(comments, count)
            }
          }
        }
      }
    } catch {
      // Ignore malformed json-ld script
    }
  }

  // 3. Facebook Relay / GraphQL Cache embedded JSON
  const reactionMatch =
    html.match(/"reaction_count":\s*\{\s*"count":\s*(\d+)/i) ||
    html.match(/"total_reaction_count":\s*(\d+)/i) ||
    html.match(/"like_count":\s*(\d+)/i) ||
    html.match(/"reaction_count":\s*(\d+)/i) ||
    html.match(/"i18n_reaction_count":\s*"([^"]+)"/i)
  if (reactionMatch && reactionMatch[1]) {
    likes = Math.max(likes, parseStatNumber(reactionMatch[1]))
  }

  const commentMatch =
    html.match(/"comment_count":\s*\{\s*"total_count":\s*(\d+)/i) ||
    html.match(/"total_comment_count":\s*(\d+)/i) ||
    html.match(/"comments":\s*\{\s*"total_count":\s*(\d+)/i) ||
    html.match(/"i18n_comment_count":\s*"([^"]+)"/i)
  if (commentMatch && commentMatch[1]) {
    comments = Math.max(comments, parseStatNumber(commentMatch[1]))
  }

  const viewMatch =
    html.match(/"video_view_count":\s*(\d+)/i) ||
    html.match(/"play_count":\s*(\d+)/i) ||
    html.match(/"view_count":\s*(\d+)/i) ||
    html.match(/"views":\s*(\d+)/i)
  if (viewMatch && viewMatch[1]) {
    views = Math.max(views, parseStatNumber(viewMatch[1]))
  }

  // 4. Fallback RegEx patterns in HTML / Meta Description
  if (views === 0) {
    const vm =
      html.match(/([\d.,]+\s*[kKmMbB]?)\s*(?:lượt xem|views|view)/i) ||
      html.match(/([\d.,]+\s*[kKmMbB]?)\s*lượt phát/i)
    if (vm && vm[1]) {
      views = Math.max(views, parseStatNumber(vm[1]))
    }
  }

  if (likes === 0) {
    const lm =
      html.match(/([\d.,]+\s*[kKmMbB]?)\s*(?:lượt thích|likes|like|người thích|cảm xúc)/i) ||
      html.match(/([\d.,]+\s*[kKmMbB]?)\s*thích/i)
    if (lm && lm[1]) {
      likes = Math.max(likes, parseStatNumber(lm[1]))
    }
  }

  if (comments === 0) {
    const cm =
      html.match(/([\d.,]+\s*[kKmMbB]?)\s*(?:bình luận|comments|comment)/i)
    if (cm && cm[1]) {
      comments = Math.max(comments, parseStatNumber(cm[1]))
    }
  }

  return { views, likes, comments }
}

export class PostStatsScanner {
  /**
   * Scans a post URL (Facebook, YouTube, TikTok, Instagram, Web) using yt-dlp + HTML scraping
   */
  public static async scanPostStats(url: string): Promise<PostStats> {
    const cleanUrl = (url || '').trim()
    const nowIso = new Date().toISOString()

    if (!cleanUrl) {
      return { views: 0, likes: 0, comments: 0, scanned_at: nowIso }
    }

    let views = 0
    let likes = 0
    let comments = 0

    // Strategy 1: Try yt-dlp metadata extraction (if binary is available)
    try {
      const ytdlp = getBinaryPath('yt-dlp')
      if (ytdlp) {
        const ytdlpPromise = new Promise<{ views: number; likes: number; comments: number } | null>(
          (resolve) => {
            const child = spawn(ytdlp, ['--dump-json', '--no-warnings', '--no-playlist', cleanUrl])
            let stdout = ''
            child.stdout.on('data', (d) => {
              stdout += d.toString()
            })
            child.on('close', (code) => {
              if (code === 0 && stdout) {
                try {
                  const json = JSON.parse(stdout)

                  // Extract metrics from title prefix, filename, and description
                  const fromTitle = parseMetricsFromText(json.title || json.fulltitle || json._filename)
                  const fromDesc = parseMetricsFromText(json.description)

                  // IMPORTANT:
                  // Facebook displays public view counts in title (e.g. "4.4K views · 53 reactions"),
                  // while json.view_count is often internal DASH playback sessions (e.g. 2127).
                  // When available, prioritize fromTitle.views for accurate UI matching!
                  const extractedViews =
                    fromTitle.views ||
                    parseStatNumber(json.view_count || json.views || fromDesc.views)

                  const extractedLikes =
                    fromTitle.likes ||
                    fromDesc.likes ||
                    parseStatNumber(json.like_count || json.likes)

                  const extractedComments =
                    fromTitle.comments ||
                    fromDesc.comments ||
                    parseStatNumber(json.comment_count || json.comments)

                  resolve({
                    views: extractedViews,
                    likes: extractedLikes,
                    comments: extractedComments
                  })
                  return
                } catch {}
              }
              resolve(null)
            })
            child.on('error', () => resolve(null))
          }
        )

        const ytdlpResult = await Promise.race([
          ytdlpPromise,
          new Promise<null>((r) => setTimeout(() => r(null), 8000))
        ])

        if (ytdlpResult) {
          views = Math.max(views, ytdlpResult.views)
          likes = Math.max(likes, ytdlpResult.likes)
          comments = Math.max(comments, ytdlpResult.comments)

          // If yt-dlp successfully retrieved views and likes, return immediately
          if (views > 0 && likes > 0) {
            return { views, likes, comments, scanned_at: nowIso }
          }
        }
      }
    } catch {
      // Non-fatal, proceed to HTML scraper
    }

    // Strategy 2: Direct HTTP scrape fallback using facebookexternalhit
    try {
      const resp = await axios.get(cleanUrl, {
        headers: {
          'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
          Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
          'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8'
        },
        timeout: 8000,
        maxRedirects: 5
      })

      const html = typeof resp.data === 'string' ? resp.data : ''
      if (html) {
        const scraped = extractStatsFromHtml(html)
        views = Math.max(views, scraped.views)
        likes = Math.max(likes, scraped.likes)
        comments = Math.max(comments, scraped.comments)
      }
    } catch {
      // Non-fatal: network error / restricted access
    }

    return {
      views,
      likes,
      comments,
      scanned_at: nowIso
    }
  }
}
