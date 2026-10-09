import axios, { AxiosInstance } from 'axios'
import * as cheerio from 'cheerio'
import fs from 'fs'
import path from 'path'
import { URL } from 'url'
import { TranslatorService, ChapterContent } from './translator'
import { CMSPublisher, StoryInfo as PublisherStoryInfo, isImageUrl } from './publisher'
import { getDatabaseService } from './database'
import { ConfigService } from './config'

export type { ChapterContent }

export interface StoryInfo {
  title: string
  slug: string
  base_url: string
  total_chapters: number
  cover_image?: string
  is_single_page?: boolean
}

export interface ScraperOptions {
  url: string
  outputDir?: string
  downloadImages?: boolean
  translateEn?: boolean
  publishCms?: boolean
  cmsUrl?: string
  cmsUser?: string
  cmsPass?: string
  startCh?: number
  endCh?: number
  delay?: number
  onLog?: (msg: string) => void
  onProgress?: (pct: number, status: string) => void
  isCancelled?: () => boolean
}

export interface ScraperResult {
  ok: boolean
  message?: string
  title?: string
  chapters_scraped?: number
  output_dir?: string
  cms_posts?: any[]
}

// ================= STRING & FILE UTILS =================

export function sanitizeFolderName(name: string): string {
  if (!name) return 'story'
  const clean = name.replace(/[<>:"/\\|?*]/g, '-').slice(0, 100).replace(/^[.\s-]+|[.\s-]+$/g, '')
  return clean || 'story'
}

export function fixMojibake(text: string): string {
  if (!text) return ''
  const replacements: Record<string, string> = {
    'â€œ': '“',
    'â€ ': '”',
    'â€”': '—',
    'â€™': '’',
    'â€˜': '‘',
    'â€¦': '…',
    'Ã¡': 'á',
    'Ã©': 'é',
    'Ã³': 'ó',
    'Ãº': 'ú',
    'Ã£': 'ã',
    'Ãµ': 'õ',
    'Ã§': 'ç',
    'Ã¢': 'â',
    'Ãª': 'ê',
    'Ã´': 'ô',
    '‚Äú': '“',
    '‚Äù': '”',
    '‚Äî': '—',
    '‚Äô': '’',
    '‚Äò': '‘',
    '‚Ä¶': '…',
    '‚Äì': '–'
  }
  let res = text
  for (const [k, v] of Object.entries(replacements)) {
    if (res.includes(k)) {
      res = res.split(k).join(v)
    }
  }
  return res
}

export function tagToMarkdown($: cheerio.CheerioAPI, node: any): string {
  if (!node) return ''
  if (node.type === 'text') {
    return node.data || ''
  }
  if (node.type !== 'tag') {
    return ''
  }

  const tagName = (node.name || '').toLowerCase()
  if (['script', 'style', 'noscript', 'iframe', 'svg', 'button', 'input', 'select'].includes(tagName)) {
    return ''
  }
  if (tagName === 'br') {
    return '\n'
  }

  let inner = ''
  if (node.children && node.children.length > 0) {
    for (const child of node.children) {
      inner += tagToMarkdown($, child)
    }
  }

  if (!inner.trim()) return inner

  const style = ($(node).attr('style') || '').toLowerCase()
  const isBold =
    ['b', 'strong'].includes(tagName) ||
    style.includes('font-weight:bold') ||
    style.includes('font-weight: bold') ||
    style.includes('font-weight:700') ||
    style.includes('font-weight: 700')
  const isItalic =
    ['i', 'em'].includes(tagName) ||
    style.includes('font-style:italic') ||
    style.includes('font-style: italic')
  const isStrike = ['s', 'del', 'strike'].includes(tagName)
  const isCode = tagName === 'code'

  let res = inner
  if (isCode) res = `\`${res.trim()}\``
  if (isStrike) res = `~~${res.trim()}~~`
  if (isItalic) res = `*${res.trim()}*`
  if (isBold) res = `**${res.trim()}**`

  return res
}

export function cleanFormattedText($: cheerio.CheerioAPI, elem: any): string {
  if (!elem) return ''
  const raw = tagToMarkdown($, elem)
  const lines = raw
    .split('\n')
    .map((l) => l.replace(/[ \t]+/g, ' ').trim())
    .filter((l) => Boolean(l))
  return fixMojibake(lines.join(' ').trim())
}

export function saveChapter(chapter: ChapterContent, outputDir: string): string {
  const chNumberStr = String(chapter.chapter_number).padStart(2, '0')
  const chapterDirName = `chapter_${chNumberStr}`
  const chapterDir = path.join(outputDir, chapterDirName)
  fs.mkdirSync(chapterDir, { recursive: true })

  const titlePath = path.join(chapterDir, 'title.md')
  fs.writeFileSync(titlePath, (chapter.title || `Chapter ${chapter.chapter_number}`).trim() + '\n', 'utf-8')

  const contentPath = path.join(chapterDir, 'content.md')
  const lines: string[] = []
  for (const [elemType, elemVal] of chapter.content_elements || []) {
    const val = (elemVal || '').trim()
    if (!val) continue
    if (elemType === 'text') {
      if (isImageUrl(val)) {
        lines.push(`![](${val})`)
      } else {
        lines.push(elemVal)
      }
      lines.push('')
    } else if (elemType === 'heading') {
      lines.push(`## ${elemVal}`)
      lines.push('')
    } else if (elemType === 'quote') {
      lines.push(`> ${elemVal}`)
      lines.push('')
    } else if (elemType === 'image') {
      lines.push(`![](${val})`)
      lines.push('')
    }
  }

  fs.writeFileSync(contentPath, lines.join('\n').trim() + '\n', 'utf-8')
  return chapterDirName
}

export function saveFullStory(chapters: ChapterContent[], storyInfo: StoryInfo, outputDir: string): string {
  const filePath = path.join(outputDir, 'full_story.md')
  const lines: string[] = [
    `# ${storyInfo.title}`,
    '',
    `**Tổng số chapter:** ${chapters.length}`,
    `**Nguồn:** ${storyInfo.base_url}`,
    '',
    '---',
    ''
  ]

  for (const chapter of chapters) {
    lines.push(`## ${chapter.title}`)
    lines.push('')
    for (const [elemType, elemVal] of chapter.content_elements || []) {
      const val = (elemVal || '').trim()
      if (!val) continue
      if (elemType === 'text') {
        if (isImageUrl(val)) {
          lines.push(`![](${val})`)
        } else {
          lines.push(elemVal)
        }
        lines.push('')
      } else if (elemType === 'heading') {
        lines.push(`### ${elemVal}`)
        lines.push('')
      } else if (elemType === 'quote') {
        lines.push(`> ${elemVal}`)
        lines.push('')
      } else if (elemType === 'image') {
        lines.push(`![](${val})`)
        lines.push('')
      }
    }
    lines.push('---')
    lines.push('')
  }

  fs.writeFileSync(filePath, lines.join('\n').trim() + '\n', 'utf-8')
  return filePath
}

export function extractCoverImage($: cheerio.CheerioAPI, baseUrl: string): string | undefined {
  let coverImage =
    $('meta[property="og:image"]').attr('content') ||
    $('meta[name="og:image"]').attr('content') ||
    $('meta[property="og:image:url"]').attr('content') ||
    $('meta[name="twitter:image"]').attr('content') ||
    $('meta[name="twitter:image:src"]').attr('content')

  if (coverImage && coverImage.trim()) {
    try {
      return new URL(coverImage.trim(), baseUrl).href
    } catch {}
  }

  const firstImg = $('img').filter((_, el) => {
    const src = $(el).attr('src') || $(el).attr('data-src') || $(el).attr('data-original') || ''
    return Boolean(src) && !src.startsWith('data:') && !/(icon|avatar|logo|badge|pixel)/i.test(src)
  }).first()

  const src = (firstImg.attr('src') || firstImg.attr('data-src') || firstImg.attr('data-original') || '').trim()
  if (src) {
    try {
      return new URL(src, baseUrl).href
    } catch {}
  }

  return undefined
}

// ================= PARSERS =================

export interface BaseParser {
  getName(): string
  getStoryInfo(html: string, url: string): StoryInfo
  parseChapter(html: string, chapterNumber: number): ChapterContent
  buildChapterUrl(baseUrl: string, chapterNumber: number, isSinglePage?: boolean): string
}

export class UniversalParser implements BaseParser {
  public chapterUrls: Map<number, string> = new Map()
  public cachedHtml: Map<string, string> = new Map()

  public getName(): string {
    return 'Universal Story Parser (Tự động thích ứng mọi website)'
  }

  private cleanTitle(text: string): string {
    if (!text) return ''
    for (const sep of [' | ', ' :: ']) {
      if (text.includes(sep)) {
        text = text.split(sep)[0]
      }
    }
    if (text.includes(' - ')) {
      const parts = text.split(' - ')
      if (!/^(?:chapter|part|chương|tập)\s*\d+$/i.test(parts[0].trim())) {
        text = parts[0]
      }
    }
    return text.trim()
  }

  private findNavUrl($: cheerio.CheerioAPI, currentUrl: string, direction: 'next' | 'prev'): string | null {
    const selectors =
      direction === 'next'
        ? ['a.series-nav__btn--next', 'a[rel="next"]', 'a.next-chapter', 'a.next', 'a.next-post', '.nav-next a']
        : ['a.series-nav__btn--prev', 'a[rel="prev"]', 'a.prev-chapter', 'a.prev', 'a.prev-post', '.nav-prev a']

    for (const sel of selectors) {
      const el = $(sel).first()
      if (el.length > 0) {
        const href = el.attr('href')
        if (href && !href.startsWith('#') && !href.startsWith('javascript:')) {
          try {
            return new URL(href, currentUrl).href
          } catch {}
        }
      }
    }

    const directWords =
      direction === 'next'
        ? ['next', 'next→', 'next >', 'next chapter', 'chương sau', 'tiếp theo']
        : ['prev', 'previous', '←prev', '←previous', '< prev', 'chương trước']

    let foundUrl: string | null = null
    $('a').each((_, a) => {
      if (foundUrl) return
      const text = $(a).text().trim().toLowerCase()
      const href = $(a).attr('href')
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) return
      if (directWords.includes(text) || (direction === 'next' && /^(?:next|tiếp|chap sau)/i.test(text))) {
        try {
          foundUrl = new URL(href, currentUrl).href
        } catch {}
      }
    })

    return foundUrl
  }

  private discoverChapters(startUrl: string, startHtml: string): { urls: Map<number, string>; isSinglePage: boolean } {
    const cleanStart = startUrl.split('?')[0].split('#')[0].replace(/\/+$/, '')
    const $ = cheerio.load(startHtml || '')
    const urls = new Map<number, string>()

    if (!startHtml) {
      urls.set(1, cleanStart)
      return { urls, isSinglePage: true }
    }

    // 1. Check TOC containers
    const tocSelectors = [
      '.chapter-list',
      '.toc-list',
      '.story-chapters',
      '.table-of-contents',
      '.chapter-toc',
      '.ql-table',
      'ol#chapter-toc-list',
      'ul.list-chapters'
    ]

    for (const sel of tocSelectors) {
      const container = $(sel).first()
      if (container.length > 0) {
        const cClasses = (container.attr('class') || '').toLowerCase()
        if (/\b(?:series-nav|pagination|pager|nav-links|breadcrumb)\b/.test(cClasses)) {
          continue
        }

        const links = container.find('a')
        if (links.length >= 2) {
          links.each((idx, a) => {
            const href = $(a).attr('href')
            const txt = $(a).text().trim()
            if (!href || href.startsWith('#') || href.startsWith('javascript:')) return
            if (/\b(?:next|prev|previous|tiếp|trước)\b/i.test(txt)) return
            try {
              const fullHref = new URL(href, startUrl).href.split('?')[0].split('#')[0]
              const m = txt.match(/(?:chapter|part|chương|tập|hồi)\s*(\d+)/i) || fullHref.match(/(?:chapter|part|chap)-(\d+)/i)
              const chNum = m ? parseInt(m[1], 10) : idx + 1
              urls.set(chNum, fullHref)
            } catch {}
          })
          if (urls.size >= 2) {
            return { urls, isSinglePage: false }
          }
        }
      }
    }

    // 2. Check general chapter link pattern on page (strictly restricted to current story base path)
    const storyBasePath = new URL(startUrl).pathname.replace(/\/(?:chapter|part|chap)[-_/]?\d+.*$/i, '').replace(/\/+$/, '')
    const allLinks = $('a[href*="chapter-"], a[href*="chap-"], a[href*="/part-"]')
    if (allLinks.length >= 2) {
      allLinks.each((_, a) => {
        const href = $(a).attr('href')
        if (!href) return
        try {
          const fullHref = new URL(href, startUrl).href.split('?')[0].split('#')[0]
          const linkPath = new URL(fullHref).pathname
          if (storyBasePath && !linkPath.startsWith(storyBasePath)) {
            return
          }
          const m = fullHref.match(/(?:chapter|part|chap)-(\d+)/i)
          if (m) {
            urls.set(parseInt(m[1], 10), fullHref)
          }
        } catch {}
      })
      if (urls.size >= 2) {
        return { urls, isSinglePage: false }
      }
    }

    // 3. Check Next button existence
    const nextBtn = this.findNavUrl($, startUrl, 'next')
    if (nextBtn) {
      urls.set(1, cleanStart)
      return { urls, isSinglePage: false }
    }

    // 4. Default: Single page story
    urls.set(1, cleanStart)
    return { urls, isSinglePage: true }
  }

  public getStoryInfo(html: string, url: string): StoryInfo {
    const cleanUrl = (url || '').split('?')[0].split('#')[0].replace(/\/+$/, '')
    const $ = cheerio.load(html || '')

    let title = ''
    const ogTitle = $('meta[property="og:title"]').attr('content')
    if (ogTitle) {
      title = this.cleanTitle(ogTitle)
    }
    if (!title) {
      const h1 = $('h1').first().text().trim()
      if (h1 && !/^(?:end of|report|comment)/i.test(h1)) {
        title = h1
      }
    }
    if (!title) {
      title = this.cleanTitle($('title').text().trim())
    }

    // Strip leading "Chapter 1 - " if present
    const cleanStoryTitle = title.replace(/^(?:chapter|part|chương|tập)\s*\d+\s*(?:[:–—\-]|\s+–\s+|\s+—\s+|\s+-\s+)\s*/i, '').trim()
    const finalTitle = cleanStoryTitle.length >= 3 ? cleanStoryTitle : title || 'Untitled Story'

    // Cover image / Featured image
    const coverImage = extractCoverImage($, url)

    const { urls, isSinglePage } = this.discoverChapters(cleanUrl, html)
    this.chapterUrls = urls

    const urlObj = new URL(cleanUrl || 'https://example.com')
    let slug = urlObj.pathname.replace(/\/+$/, '').split('/').pop() || 'story'
    slug = slug.replace(/^(?:chapter|part|chap)-\d+-?/i, '') || 'story'

    let baseUrl = cleanUrl
    if (!isSinglePage) {
      baseUrl = cleanUrl.replace(/\/(?:chapter|part|chap)[-_/]?\d+.*$/i, '')
    }

    return {
      title: finalTitle,
      slug,
      base_url: baseUrl,
      total_chapters: urls.size || 1,
      cover_image: coverImage,
      is_single_page: isSinglePage
    }
  }

  public buildChapterUrl(baseUrl: string, chapterNumber: number, isSinglePage = false): string {
    if (isSinglePage) return baseUrl
    if (this.chapterUrls.has(chapterNumber)) {
      return this.chapterUrls.get(chapterNumber)!
    }
    return `${baseUrl}/chapter-${chapterNumber}`
  }

  public parseChapter(html: string, chapterNumber: number): ChapterContent {
    const $ = cheerio.load(html || '')
    let title = ''

    const ogTitle = $('meta[property="og:title"]').attr('content')
    if (ogTitle && /(?:chapter|part|chương)\b/i.test(ogTitle)) {
      title = this.cleanTitle(ogTitle)
    }
    if (!title) {
      const h1 = $('h1').first().text().trim()
      if (h1 && !/^(?:end of|report|comment)/i.test(h1)) {
        title = h1
      }
    }
    if (!title) {
      title = this.cleanTitle($('title').text().trim())
    }
    if (!title) {
      title = `Chapter ${chapterNumber}`
    }

    // Content container detection
    const selectors = [
      '.inkitt-reader__content',
      '.module-article-content__body',
      '.v5-prose',
      '.v4-prose',
      '.prose',
      '.entry-content',
      '.post-content',
      '.article-content',
      '.chapter-content',
      '.story-content',
      '.reading-content',
      'article',
      '[itemprop="articleBody"]',
      'main'
    ]

    let contentContainer: cheerio.Cheerio<any> = $('body')
    for (const sel of selectors) {
      const el = $(sel).first()
      if (el.length > 0 && el.find('p').length >= 1) {
        contentContainer = el
        break
      }
    }

    // Clean noise tags
    contentContainer.find('script, style, noscript, iframe, svg, form, .ads-banner, .social-share, .report, .comment').remove()

    const paragraphs: string[] = []
    const images: string[] = []
    const contentElements: Array<[string, string]> = []

    contentContainer.find('h2, h3, h4, p, blockquote, img').each((_, elem) => {
      const tagName = (elem.name || '').toLowerCase()

      if (['h2', 'h3', 'h4'].includes(tagName)) {
        const txt = cleanFormattedText($, elem)
        if (txt && !/^(?:end of|report this|share this)/i.test(txt)) {
          paragraphs.push(txt)
          contentElements.push(['heading', txt])
        }
      } else if (tagName === 'blockquote') {
        const txt = cleanFormattedText($, elem)
        if (txt) {
          paragraphs.push(txt)
          contentElements.push(['quote', txt])
        }
      } else if (tagName === 'p') {
        if ($(elem).parents('blockquote').length > 0) return
        const txt = cleanFormattedText($, elem)
        if (txt && !/^(?:end of|report this|select a reason)/i.test(txt)) {
          if (isImageUrl(txt)) {
            if (!images.includes(txt)) {
              images.push(txt)
            }
            contentElements.push(['image', txt])
          } else {
            paragraphs.push(txt)
            contentElements.push(['text', txt])
          }
        }
      } else if (tagName === 'img') {
        const src = $(elem).attr('src') || $(elem).attr('data-src') || $(elem).attr('data-original') || ''
        if (src && !src.startsWith('data:') && !/(icon|avatar|logo|badge|pixel)/i.test(src)) {
          if (!images.includes(src)) {
            images.push(src)
            contentElements.push(['image', src])
          }
        }
      }
    })

    return {
      chapter_number: chapterNumber,
      title,
      paragraphs,
      images,
      content_elements: contentElements
    }
  }
}

export class AHCMSParser implements BaseParser {
  public getName(): string {
    return 'AH CMS Parser (fast2tricks.com)'
  }

  public getStoryInfo(html: string, url: string): StoryInfo {
    const $ = cheerio.load(html || '')
    let title = ''
    const ogTitle = $('meta[property="og:title"]').attr('content')
    if (ogTitle) {
      const raw = ogTitle.split('|')[0].trim()
      title = raw.includes('—') ? raw.split('—').pop()!.trim() : raw
    }
    if (!title) {
      title = $('h1.pst-title').text().trim() || 'AH CMS Story'
    }

    const cleanUrl = url.split('?')[0].split('#')[0].replace(/\/+$/, '')
    const urlObj = new URL(cleanUrl)
    const slug = urlObj.pathname.replace(/\/chapter-\d+$/i, '').split('/').pop() || 'story'
    const baseUrl = `${urlObj.origin}/${slug}`

    let total = 0
    // 1. Check breadcrumb "CHAPTER X OF Y" or "Chapter X / Y"
    const bcText = $('.pst-bc-chapter, .breadcrumb, body').text()
    const bcMatch = bcText.match(/chapter\s+\d+\s+(?:of|\/)\s+(\d+)/i)
    if (bcMatch) {
      total = parseInt(bcMatch[1], 10)
    }

    // 2. Quick links table - only take the first container (desktop) to avoid duplicates
    if (total === 0) {
      const qlTable = $('ul.ql-table').first()
      if (qlTable.length > 0) {
        total = qlTable.find('li').length
      }
    }

    if (total === 0) {
      const mobileItems = $('[data-chapter-search]')
      if (mobileItems.length > 0) {
        total = mobileItems.length
      }
    }

    // 3. Find max chapter number from story links
    if (total === 0) {
      $('a[href*="/chapter-"]').each((_, a) => {
        const m = ($(a).attr('href') || '').match(/\/chapter-(\d+)/)
        if (m) total = Math.max(total, parseInt(m[1], 10))
      })
    }

    const coverImage = extractCoverImage($, url)

    return {
      title,
      slug,
      base_url: baseUrl,
      total_chapters: total || 1,
      cover_image: coverImage,
      is_single_page: total === 0
    }
  }

  public buildChapterUrl(baseUrl: string, chapterNumber: number): string {
    return `${baseUrl}/chapter-${chapterNumber}`
  }

  public parseChapter(html: string, chapterNumber: number): ChapterContent {
    const universal = new UniversalParser()
    return universal.parseChapter(html, chapterNumber)
  }
}

export class TreeIQParser implements BaseParser {
  public getName(): string {
    return 'TreeIQ Parser (treeiq.biz)'
  }

  public getStoryInfo(html: string, url: string): StoryInfo {
    const $ = cheerio.load(html || '')
    const title = $('h1.v5-title').text().trim() || $('title').text().split('|')[0].trim() || 'TreeIQ Story'
    const cleanUrl = url.split('?')[0].split('#')[0].replace(/\/+$/, '')
    const urlObj = new URL(cleanUrl)

    let total = 0

    // Priority 1: Check breadcrumb/info text "Chapter X / Y" (identical to ban_win)
    const chapterInfo = $('span').filter((_, el) => /Chapter\s+\d+\s*\/\s*\d+/i.test($(el).text())).first()
    if (chapterInfo.length > 0) {
      const m = chapterInfo.text().match(/Chapter\s+\d+\s*\/\s*(\d+)/i)
      if (m) total = parseInt(m[1], 10)
    }
    if (total === 0) {
      const text = $('body').text()
      const m = text.match(/Chapter\s+\d+\s*\/\s*(\d+)/i)
      if (m) total = parseInt(m[1], 10)
    }

    // Priority 2: Desktop TOC first; if absent, mobile TOC (never combine both with comma!)
    if (total === 0) {
      const desktopToc = $('ol#chapter-toc-list-desktop').first()
      const mobileToc = $('ol#chapter-toc-list').first()
      const toc = desktopToc.length > 0 ? desktopToc : mobileToc

      if (toc.length > 0) {
        // Count actual chapter links or find max chapter number
        let maxCh = 0
        toc.find('a[href*="/chapter-"]').each((_, a) => {
          const match = ($(a).attr('href') || '').match(/\/chapter-(\d+)/)
          if (match) maxCh = Math.max(maxCh, parseInt(match[1], 10))
        })

        if (maxCh > 0) {
          total = maxCh
        } else {
          total = toc.find('li').length
        }
      }
    }

    // Priority 3: Max chapter number from all chapter links on page
    if (total === 0) {
      $('a[href*="/chapter-"]').each((_, a) => {
        const match = ($(a).attr('href') || '').match(/\/chapter-(\d+)/)
        if (match) total = Math.max(total, parseInt(match[1], 10))
      })
    }

    const basePath = urlObj.pathname.replace(/\/chapter-\d+$/i, '')
    const slug = basePath.split('/').pop() || 'story'
    const baseUrl = `${urlObj.origin}${basePath}`
    const coverImage = extractCoverImage($, url)

    return {
      title,
      slug,
      base_url: baseUrl,
      total_chapters: total || 1,
      cover_image: coverImage,
      is_single_page: total === 0
    }
  }

  public buildChapterUrl(baseUrl: string, chapterNumber: number): string {
    return `${baseUrl}/chapter-${chapterNumber}`
  }

  public parseChapter(html: string, chapterNumber: number): ChapterContent {
    const universal = new UniversalParser()
    return universal.parseChapter(html, chapterNumber)
  }
}

export function detectParser(url: string): BaseParser {
  if (!url) return new UniversalParser()
  try {
    const hostname = new URL(url).hostname.toLowerCase()
    if (hostname.endsWith('treeiq.biz')) {
      return new TreeIQParser()
    }
    if (hostname.endsWith('fast2tricks.com')) {
      return new AHCMSParser()
    }
  } catch {}
  return new UniversalParser()
}

// ================= STORY SCRAPER ENGINE =================

export class StoryScraperEngine {
  private onLog: (msg: string) => void
  private onProgress: (pct: number, status: string) => void
  private isCancelledFn: () => boolean
  private client: AxiosInstance

  constructor(options?: {
    onLog?: (msg: string) => void
    onProgress?: (pct: number, status: string) => void
    isCancelled?: () => boolean
  }) {
    this.onLog = options?.onLog || (() => {})
    this.onProgress = options?.onProgress || (() => {})
    this.isCancelledFn = options?.isCancelled || (() => false)
    this.client = axios.create({
      timeout: 30000,
      headers: {
        'User-Agent':
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8'
      }
    })
  }

  private log(msg: string): void {
    this.onLog(msg)
  }

  private progress(pct: number, status: string): void {
    this.onProgress(pct, status)
  }

  public async fetchHtml(url: string, retries = 3, delay = 1.0): Promise<string | null> {
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        const res = await this.client.get(url)
        if (res.status === 200 && typeof res.data === 'string') {
          return fixMojibake(res.data)
        }
      } catch (err: any) {
        if (attempt < retries) {
          await new Promise((r) => setTimeout(r, delay * 1000 * attempt))
        } else {
          this.log(`  ❌ Lỗi tải URL ${url}: ${err.message}`)
          return null
        }
      }
    }
    return null
  }

  public async downloadImage(url: string, savePath: string): Promise<boolean> {
    if (fs.existsSync(savePath)) return true
    fs.mkdirSync(path.dirname(savePath), { recursive: true })

    try {
      const response = await axios({
        url,
        method: 'GET',
        responseType: 'arraybuffer',
        timeout: 25000,
        headers: {
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
      })
      if (response.status === 200 && response.data) {
        fs.writeFileSync(savePath, Buffer.from(response.data))
        return true
      }
    } catch {}
    return false
  }

  public async run(options: ScraperOptions): Promise<ScraperResult> {
    const url = (options.url || '').trim()
    if (!url) {
      const err = '❌ Chưa nhập URL trang truyện.'
      this.log(err)
      return { ok: false, message: err }
    }

    if (this.isCancelledFn()) {
      return { ok: false, message: 'Đã hủy thao tác' }
    }

    this.progress(5, 'Đang phân tích cấu trúc trang web...')
    this.log(`🔍 Phân tích URL: ${url}`)

    const parser = detectParser(url)
    this.log(`✅ Đã nhận diện: ${parser.getName()}`)

    this.progress(10, 'Đang tải trang để lấy thông tin truyện...')
    this.log('📥 Đang tải trang để lấy thông tin truyện...')

    const html = await this.fetchHtml(url, 3, options.delay || 1.0)
    if (!html) {
      const err = '❌ Không thể tải trang. Vui lòng kiểm tra lại URL hoặc kết nối mạng.'
      this.log(err)
      return { ok: false, message: err }
    }

    let storyInfo: StoryInfo
    try {
      storyInfo = parser.getStoryInfo(html, url)
    } catch (err: any) {
      const errMsg = `❌ Lỗi khi phân tích thông tin truyện: ${err.message}`
      this.log(errMsg)
      return { ok: false, message: errMsg }
    }

    const translateEn = options.translateEn ?? true
    const translator = translateEn ? new TranslatorService('en') : null

    // Translate title if enabled
    if (translator && storyInfo.title) {
      this.log('🌐 Đang dịch tên truyện sang tiếng Anh...')
      try {
        const transTitle = await translator.translateText(storyInfo.title)
        if (transTitle && transTitle !== storyInfo.title) {
          storyInfo.title = transTitle
          this.log(`🌐 Tên truyện tiếng Anh: ${storyInfo.title}`)
        }
      } catch (err: any) {
        this.log(`⚠️ Dịch tên truyện cảnh báo: ${err.message}`)
      }
    }

    this.log(`📚 Tên truyện: ${storyInfo.title}`)
    this.log(`🔗 Nguồn: ${storyInfo.base_url}`)

    const totalChapters = storyInfo.total_chapters || 1
    const fromCh = Math.max(1, options.startCh || 1)
    const toCh = options.endCh && options.endCh > 0 ? options.endCh : totalChapters

    const sCh = Math.min(fromCh, totalChapters)
    const eCh = Math.min(Math.max(sCh, toCh), totalChapters)
    const totalToDownload = eCh - sCh + 1

    this.log(`📋 Sẽ xử lý chapter ${sCh} → ${eCh} (${totalToDownload} chapters)`)

    // Output directory
    const defaultOutput = path.join(process.cwd(), 'output')
    const baseOut = options.outputDir || defaultOutput
    const storyDirName = sanitizeFolderName(storyInfo.slug || storyInfo.title)
    const outStoryDir = path.join(baseOut, storyDirName)
    const imagesDir = path.join(outStoryDir, 'images')

    fs.mkdirSync(outStoryDir, { recursive: true })
    if (options.downloadImages) {
      fs.mkdirSync(imagesDir, { recursive: true })
    }

    const chapters: ChapterContent[] = []
    const downloadImages = options.downloadImages ?? true
    const delaySec = options.delay ?? 1.0
    let consecutiveFails = 0

    for (let idx = 1; idx <= totalToDownload; idx++) {
      if (this.isCancelledFn()) {
        this.log('⚠️ Quá trình bị người dùng hủy bỏ.')
        break
      }

      const chNum = sCh + idx - 1
      const pct = 15.0 + (idx / totalToDownload) * 70.0
      this.progress(pct, `[${idx}/${totalToDownload}] Đang tải Chapter ${chNum}...`)
      this.log(`📄 [${idx}/${totalToDownload}] Đang tải Chapter ${chNum}...`)

      const chUrl = parser.buildChapterUrl(storyInfo.base_url, chNum, storyInfo.is_single_page)

      let chHtml: string | null = null
      if (storyInfo.is_single_page && chNum === 1) {
        chHtml = html
        this.log('   ♻ Sử dụng cache từ lần tải đầu')
      } else {
        chHtml = await this.fetchHtml(chUrl, 3, delaySec)
        if (idx < totalToDownload && delaySec > 0) {
          await new Promise((r) => setTimeout(r, delaySec * 1000))
        }
      }

      if (!chHtml) {
        this.log(`   ❌ Thất bại khi tải Chapter ${chNum}`)
        consecutiveFails++
        if (consecutiveFails >= 2 && chapters.length > 0) {
          this.log(`   ℹ️ Đã dừng do 2 chapter liên tiếp không tồn tại (đã cào xong ${chapters.length} chapter).`)
          break
        }
        continue
      }
      consecutiveFails = 0

      let chapter: ChapterContent
      try {
        chapter = parser.parseChapter(chHtml, chNum)
      } catch (err: any) {
        this.log(`   ❌ Lỗi phân tích Chapter ${chNum}: ${err.message}`)
        continue
      }

      this.log(`   📝 Chapter ${chNum}: ${chapter.paragraphs.length} đoạn văn, ${(chapter.images || []).length} ảnh`)

      // Normalize images with URL resolution
      if (chapter.images && chapter.images.length > 0) {
        chapter.images = chapter.images.map((img) => {
          try {
            return new URL(img, chUrl).href
          } catch {
            return img
          }
        })
      }

      // Normalize content_elements image URLs
      if (chapter.content_elements && chapter.content_elements.length > 0) {
        chapter.content_elements = chapter.content_elements.map(([elemType, elemVal]) => {
          if (elemType === 'image' || isImageUrl(elemVal)) {
            try {
              return [elemType, new URL(elemVal, chUrl).href]
            } catch {
              return [elemType, elemVal]
            }
          }
          return [elemType, elemVal]
        })
      }

      // Auto-detect Featured image URL if storyInfo.cover_image was not set
      if (!storyInfo.cover_image) {
        if (chapter.images && chapter.images.length > 0 && isImageUrl(chapter.images[0])) {
          storyInfo.cover_image = chapter.images[0]
          this.log(`   🖼️ Tự động nhận diện Featured image URL từ Chapter ${chNum}: ${storyInfo.cover_image}`)
        } else {
          const imgElem = chapter.content_elements?.find(([t, v]) => (t === 'image' || isImageUrl(v)) && isImageUrl(v))
          if (imgElem) {
            storyInfo.cover_image = imgElem[1].trim()
            this.log(`   🖼️ Tự động nhận diện Featured image URL từ nội dung Chapter ${chNum}: ${storyInfo.cover_image}`)
          }
        }
      }

      // Download images if requested
      if (downloadImages && chapter.images && chapter.images.length > 0) {
        for (let iIdx = 0; iIdx < chapter.images.length; iIdx++) {
          const imgUrl = chapter.images[iIdx]
          const ext = path.extname(new URL(imgUrl, 'https://example.com').pathname) || '.webp'
          const imgFileName = `chapter-${String(chNum).padStart(2, '0')}-img-${String(iIdx + 1).padStart(2, '0')}${ext}`
          const imgPath = path.join(imagesDir, imgFileName)
          await this.downloadImage(imgUrl, imgPath)
        }
      }

      // Translate chapter if enabled
      if (translator) {
        this.log(`   🌐 Đang dịch Chapter ${chNum} sang tiếng Anh...`)
        try {
          chapter = await translator.translateChapter(chapter)
          this.log(`   ✅ Tiêu đề EN: ${(chapter.title || '').slice(0, 60)}...`)
        } catch (err: any) {
          this.log(`   ⚠️ Lỗi dịch Chapter ${chNum}: ${err.message}`)
        }
      }

      // Save local chapter files
      const chDirName = saveChapter(chapter, outStoryDir)
      chapters.push(chapter)
      this.log(`   💾 Đã lưu local: ${chDirName}/ (title.md, content.md)`)
    }

    // Save full story compilation
    if (chapters.length > 0) {
      saveFullStory(chapters, storyInfo, outStoryDir)
      this.log('📝 Đã tạo file tổng hợp full_story.md')
    }

    // Download cover image if present
    if (downloadImages && storyInfo.cover_image) {
      try {
        const coverExt = path.extname(new URL(storyInfo.cover_image).pathname) || '.webp'
        const coverPath = path.join(outStoryDir, `cover${coverExt}`)
        const ok = await this.downloadImage(storyInfo.cover_image, coverPath)
        if (ok) this.log(`🖼️ Đã lưu ảnh cover: cover${coverExt}`)
      } catch {}
    }

    // Publish to CMS if enabled
    let cmsPosts: any[] = []
    if (options.publishCms && chapters.length > 0) {
      const cUrl = options.cmsUrl || ConfigService.get('cms_url') || 'https://vmnewstoryus.cfx.bz'
      const cUser = options.cmsUser || ConfigService.get('cms_user') || 'admin'
      const cPass = options.cmsPass || ConfigService.get('cms_pass') || ''

      this.log(`🚀 Bắt đầu đăng lên CMS (${cUrl}) với user '${cUser}'...`)
      const publisher = new CMSPublisher(cUrl, cUser, cPass)
      const loginOk = await publisher.login()

      if (loginOk) {
        this.log(`🔑 Đăng nhập CMS thành công (User: ${cUser})!`)
        const created = await publisher.publishStory(storyInfo as PublisherStoryInfo, chapters, (msg) => {
          this.log(msg)
        })
        if (created && created.length > 0) {
          cmsPosts = created
          this.log(`🎉 Đăng bài thành công (${created.length}/${chapters.length} posts đã tạo trên CMS)!`)
        } else {
          this.log(`❌ Lỗi đăng bài lên CMS: ${publisher.lastError || 'Kiểm tra log lỗi'}`)
        }
      } else {
        this.log(`❌ Đăng nhập CMS thất bại: ${publisher.lastError || 'Sai URL hoặc mật khẩu'}`)
      }
    }

    // Save to SQLite
    try {
      getDatabaseService().addScrapedStory({
        url,
        title: storyInfo.title,
        slug: storyDirName,
        chapters_count: chapters.length,
        output_dir: outStoryDir,
        translated: translateEn ? 1 : 0,
        published: options.publishCms && cmsPosts.length > 0 ? 1 : 0,
        cms_url: options.cmsUrl || ''
      })
    } catch (err: any) {
      console.warn(`[StoryScraperEngine] DB save error: ${err.message}`)
    }

    this.progress(100, 'Hoàn tất!')
    this.log(`🎉 ĐÃ HOÀN TẤT! Đã lưu ${chapters.length} chapter vào: ${outStoryDir}`)

    return {
      ok: true,
      title: storyInfo.title,
      chapters_scraped: chapters.length,
      output_dir: outStoryDir,
      cms_posts: cmsPosts
    }
  }
}
