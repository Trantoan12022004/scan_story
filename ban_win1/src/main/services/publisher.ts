import axios, { AxiosInstance } from 'axios'
import * as cheerio from 'cheerio'
import { generateSlug, splitChapterByParts, ChapterContent, isImageUrl } from './translator'
export { isImageUrl }

export interface StoryInfo {
  title: string
  slug: string
  cover_image?: string
}

export class SimpleCookieJar {
  private cookies: Map<string, string> = new Map()

  public setCookiesFromHeaders(headers: Record<string, any> | undefined): void {
    if (!headers) return
    const raw = headers['set-cookie']
    if (!raw) return
    const list = Array.isArray(raw) ? raw : [raw]
    for (const c of list) {
      if (typeof c !== 'string') continue
      const part = c.split(';')[0]
      const eqIdx = part.indexOf('=')
      if (eqIdx !== -1) {
        const key = part.substring(0, eqIdx).trim()
        const val = part.substring(eqIdx + 1).trim()
        if (key) {
          this.cookies.set(key, val)
        }
      }
    }
  }

  public getCookieHeader(): string {
    return Array.from(this.cookies.entries())
      .map(([k, v]) => `${k}=${v}`)
      .join('; ')
  }

  public clear(): void {
    this.cookies.clear()
  }

  public size(): number {
    return this.cookies.size
  }

  public get(name: string): string | undefined {
    return this.cookies.get(name)
  }
}


export function markdownToHtmlFormatting(text: string): string {
  if (!text) return ''
  let res = text
  res = res.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
  res = res.replace(/___(.+?)___/g, '<strong><em>$1</em></strong>')
  res = res.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  res = res.replace(/__(.+?)__/g, '<strong>$1</strong>')
  res = res.replace(/(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
  res = res.replace(/(?<!\w)_(?!_)([^_]+?)(?<!_)_(?!\w)/g, '<em>$1</em>')
  res = res.replace(/~~(.+?)~~/g, '<del>$1</del>')
  return res
}

export function buildChapterDescription(coverUrl: string, chapter: ChapterContent): string {
  const htmlParts: string[] = []
  let imageInserted = false

  if (coverUrl && coverUrl.trim() && (coverUrl.startsWith('http://') || coverUrl.startsWith('https://'))) {
    const trimmedCover = coverUrl.trim()
    htmlParts.push(`<p><img src="${trimmedCover}" alt=""></p>`)
    imageInserted = true
  }

  for (const [elemType, elemVal] of chapter.content_elements || []) {
    const val = (elemVal || '').trim()
    if (!val) continue

    if (elemType === 'image' || isImageUrl(val)) {
      if (!imageInserted && (val.startsWith('http://') || val.startsWith('https://'))) {
        htmlParts.push(`<p><img src="${val}" alt=""></p>`)
        imageInserted = true
      }
      continue
    }

    if (elemType === 'heading') {
      const formatted = markdownToHtmlFormatting(val)
      htmlParts.push(`<h2>${formatted}</h2>`)
    } else if (elemType === 'quote') {
      const formatted = markdownToHtmlFormatting(val)
      htmlParts.push(`<blockquote><p>${formatted}</p></blockquote>`)
    } else {
      let cleanVal = val
      if (imageInserted) {
        cleanVal = cleanVal.replace(/!\[(.*?)\]\((https?:\/\/[^\s)]+)\)/g, '').trim()
      } else {
        const match = cleanVal.match(/!\[(.*?)\]\((https?:\/\/[^\s)]+)\)/)
        if (match) {
          htmlParts.push(`<p><img src="${match[2]}" alt="${match[1] || ''}"></p>`)
          imageInserted = true
          cleanVal = cleanVal.replace(/!\[(.*?)\]\((https?:\/\/[^\s)]+)\)/g, '').trim()
        }
      }
      if (cleanVal) {
        const formatted = markdownToHtmlFormatting(cleanVal)
        htmlParts.push(`<p>${formatted}</p>`)
      }
    }
  }

  return htmlParts.join('')
}

export function formatChapterTitleTreeIQ(title: string, chapterIdx: number): string {
  const clean = (title || '').trim()
  const m = clean.match(/^(?:CHAPTER|CHƯƠNG|PART)\s*(\d+)\s*[-:—–]?\s*(.*)$/i)
  if (m) {
    const num = m[1]
    const sub = m[2].trim()
    return sub ? `CHAPTER ${num} — ${sub.toUpperCase()}` : `CHAPTER ${num}`
  }
  const mNum = clean.match(/^(\d+)\.?\s*(.*)$/)
  if (mNum) {
    const num = mNum[1]
    const sub = mNum[2].trim()
    return sub ? `CHAPTER ${num} — ${sub.toUpperCase()}` : `CHAPTER ${num}`
  }
  return clean ? `CHAPTER ${chapterIdx} — ${clean.toUpperCase()}` : `CHAPTER ${chapterIdx}`
}

export function generateTreeIQSlug(title: string, baseSlug?: string): string {
  const base = generateSlug(baseSlug || title || 'story') || 'story'
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  let suffix = ''
  for (let i = 0; i < 6; i++) {
    suffix += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return `${base.slice(0, 100).replace(/-+$/, '')}-${suffix}`
}

export function buildTreeIQExcerpt(chapters: ChapterContent[], maxWords = 90): string {
  if (!chapters || chapters.length === 0) return ''
  const ch1 = chapters[0]
  const firstTitle = formatChapterTitleTreeIQ(ch1.title, 1)
  const texts: string[] = [firstTitle]
  for (const p of ch1.paragraphs || []) {
    const cleanP = p.replace(/<[^>]+>/g, '').trim()
    if (cleanP) texts.push(cleanP)
    const wordCount = texts.reduce((acc, t) => acc + t.split(/\s+/).filter(Boolean).length, 0)
    if (wordCount >= maxWords) break
  }
  const combined = texts.join(' ')
  const words = combined.split(/\s+/).filter(Boolean)
  if (words.length > maxWords) {
    return words.slice(0, maxWords).join(' ')
  }
  return combined
}

export function buildTreeIQBodyHtml(chapters: ChapterContent[]): string {
  const htmlParts: string[] = []
  for (let idx = 0; idx < chapters.length; idx++) {
    const ch = chapters[idx]
    const heading = formatChapterTitleTreeIQ(ch.title, idx + 1)
    htmlParts.push(`<h2>${heading}</h2>`)

    // 1. Tìm đúng 1 ảnh đại diện duy nhất cho chương này
    let chapterImage = ''
    if (ch.images && ch.images.length > 0) {
      for (const img of ch.images) {
        if (img && (img.startsWith('http://') || img.startsWith('https://'))) {
          chapterImage = img.trim()
          break
        }
      }
    }

    if (!chapterImage && ch.content_elements && ch.content_elements.length > 0) {
      for (const [elemType, elemVal] of ch.content_elements) {
        const val = (elemVal || '').trim()
        if (elemType === 'image' && (val.startsWith('http://') || val.startsWith('https://'))) {
          chapterImage = val
          break
        }
        if (isImageUrl(val)) {
          chapterImage = val
          break
        }
        const m = val.match(/!\[.*?\]\((https?:\/\/[^\s)]+)\)/)
        if (m) {
          chapterImage = m[1]
          break
        }
      }
    }

    // 2. Chèn duy nhất 1 ảnh ngay sau tiêu đề chương
    let hasInsertedImage = false
    if (chapterImage) {
      htmlParts.push(`<p><img src="${chapterImage}" alt="" loading="lazy" decoding="async" /></p>`)
      hasInsertedImage = true
    }

    // 3. Duyệt nội dung và bỏ qua bất kỳ ảnh nào khác
    if (ch.content_elements && ch.content_elements.length > 0) {
      for (const [elemType, elemVal] of ch.content_elements) {
        const val = (elemVal || '').trim()
        if (!val) continue

        if (elemType === 'image' || isImageUrl(val)) {
          if (!hasInsertedImage && (val.startsWith('http://') || val.startsWith('https://'))) {
            htmlParts.push(`<p><img src="${val}" alt="" loading="lazy" decoding="async" /></p>`)
            hasInsertedImage = true
          }
          continue
        }

        if (elemType === 'heading') {
          htmlParts.push(`<h3>${markdownToHtmlFormatting(val)}</h3>`)
        } else if (elemType === 'quote') {
          htmlParts.push(`<blockquote><p>${markdownToHtmlFormatting(val)}</p></blockquote>`)
        } else if (elemType === 'text') {
          let cleanVal = val
          if (hasInsertedImage) {
            cleanVal = cleanVal.replace(/!\[.*?\]\(https?:\/\/[^\s)]+\)/g, '').trim()
          } else {
            const m = cleanVal.match(/!\[.*?\]\((https?:\/\/[^\s)]+)\)/)
            if (m) {
              htmlParts.push(`<p><img src="${m[1]}" alt="" loading="lazy" decoding="async" /></p>`)
              hasInsertedImage = true
              cleanVal = cleanVal.replace(/!\[.*?\]\(https?:\/\/[^\s)]+\)/g, '').trim()
            }
          }
          if (cleanVal) {
            htmlParts.push(`<p>${markdownToHtmlFormatting(cleanVal)}</p>`)
          }
        }
      }
    } else {
      for (const p of ch.paragraphs || []) {
        let cleanP = (p || '').trim()
        if (!cleanP) continue
        if (hasInsertedImage) {
          cleanP = cleanP.replace(/!\[.*?\]\(https?:\/\/[^\s)]+\)/g, '').trim()
        } else {
          const m = cleanP.match(/!\[.*?\]\((https?:\/\/[^\s)]+)\)/)
          if (m) {
            htmlParts.push(`<p><img src="${m[1]}" alt="" loading="lazy" decoding="async" /></p>`)
            hasInsertedImage = true
            cleanP = cleanP.replace(/!\[.*?\]\(https?:\/\/[^\s)]+\)/g, '').trim()
          }
        }
        if (cleanP) {
          htmlParts.push(`<p>${markdownToHtmlFormatting(cleanP)}</p>`)
        }
      }
    }
  }
  return htmlParts.join('\n')
}

export function buildTreeIQBodyText(chapters: ChapterContent[]): string {
  const blocks: string[] = []
  for (let idx = 0; idx < chapters.length; idx++) {
    const ch = chapters[idx]
    const heading = formatChapterTitleTreeIQ(ch.title, idx + 1)
    const paras = (ch.paragraphs || []).map((p) => p.trim()).filter(Boolean)
    blocks.push(`${heading}\n\n${paras.join('\n\n')}`)
  }
  return blocks.join('\n\n\n')
}

export function resolveFeaturedImageUrl(coverImage?: string, baseUrl?: string): string {
  if (!coverImage) return ''
  const trimmed = coverImage.trim()
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed
  if (trimmed.startsWith('/') && baseUrl && (baseUrl.startsWith('http://') || baseUrl.startsWith('https://'))) {
    try {
      return new URL(trimmed, baseUrl).toString()
    } catch {
      return ''
    }
  }
  return ''
}

export type CMSType = 'auto' | 'blogbio' | 'treeiq'

export interface CMSPublisherOptions {
  type?: CMSType
  categoryId?: string
}

export interface CMSCategory {
  id: string
  name: string
}

export class CMSPublisher {
  private baseUrl: string
  private username: string
  private pass: string
  private client: AxiosInstance
  private csrfToken: string | null = null
  public cookieJar: SimpleCookieJar
  public lastError = ''
  public cmsType: 'blogbio' | 'treeiq' = 'blogbio'
  public categoryId = '9'
  public availableCategories: CMSCategory[] = []
  private customCategoryProvided = false

  constructor(
    baseUrl: string,
    username: string,
    pass: string,
    options?: CMSPublisherOptions
  ) {
    this.baseUrl = baseUrl.trim().replace(/\/+$/, '')
    this.username = username.trim()
    this.pass = pass.trim()
    if (options?.categoryId) {
      this.categoryId = options.categoryId.trim()
      this.customCategoryProvided = true
    }

    const lowerUrl = this.baseUrl.toLowerCase()
    if (options?.type && options.type !== 'auto') {
      this.cmsType = options.type
    } else if (lowerUrl.includes('teasy.live') || lowerUrl.includes('treeiq')) {
      this.cmsType = 'treeiq'
    } else {
      this.cmsType = 'blogbio'
    }

    this.cookieJar = new SimpleCookieJar()
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 30000,
      headers: {
        'User-Agent':
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    })
  }

  public async login(): Promise<boolean> {
    try {
      this.lastError = ''
      this.cookieJar.clear()
      this.csrfToken = null

      const loginUrl = `${this.baseUrl}/login`
      const r1 = await this.client.get(loginUrl, {
        headers: {
          Cookie: this.cookieJar.getCookieHeader()
        },
        validateStatus: (s) => s >= 200 && s < 500
      })
      this.cookieJar.setCookiesFromHeaders(r1.headers)

      if (r1.status !== 200) {
        this.lastError = `Không thể tải trang login (HTTP ${r1.status})`
        return false
      }

      const $1 = cheerio.load(r1.data)
      const token = $1('input[name="_token"]').val()

      // If no _token is found on the login form, check if this is TreeIQ CMS
      if (
        !token &&
        (this.cmsType === 'treeiq' ||
          $1('form[action="/login"]').length > 0 ||
          this.baseUrl.includes('teasy') ||
          this.baseUrl.includes('treeiq'))
      ) {
        this.cmsType = 'treeiq'
        return this.loginTreeIQFlow()
      }

      // Default BlogBio (Laravel) requires _token
      if (!token) {
        this.lastError = 'Không tìm thấy _token trong trang login (kiểm tra lại CMS URL).'
        return false
      }

      this.cmsType = 'blogbio'
      return this.loginBlogBioFlow(String(token))
    } catch (err: any) {
      this.lastError = `Lỗi kết nối CMS: ${err.message}`
      return false
    }
  }

  private async loginBlogBioFlow(token: string): Promise<boolean> {
    const loginUrl = `${this.baseUrl}/login`
    const postData = new URLSearchParams()
    postData.append('_token', token)
    postData.append('email', this.username)
    postData.append('password', this.pass)
    postData.append('remember', '1')

    // Do NOT follow redirects automatically so we capture the Set-Cookie headers from the 302 response
    const r2 = await this.client.post(loginUrl, postData.toString(), {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        Cookie: this.cookieJar.getCookieHeader()
      },
      maxRedirects: 0,
      validateStatus: (status) => status >= 200 && status < 400
    })
    this.cookieJar.setCookiesFromHeaders(r2.headers)

    // If status is 200, check if error alert was returned
    if (r2.status === 200 && r2.data && typeof r2.data === 'string') {
      const $2 = cheerio.load(r2.data)
      const errorBox = $2('.alert-danger, .invalid-feedback, .error-msg, .text-danger').first().text().trim()
      if (errorBox) {
        this.lastError = `Sai tài khoản hoặc mật khẩu: ${errorBox}`
        return false
      }
    }

    // Check admin page for CSRF token
    const adminUrl = `${this.baseUrl}/admin/posts/new`
    const r3 = await this.client.get(adminUrl, {
      headers: {
        Cookie: this.cookieJar.getCookieHeader()
      },
      maxRedirects: 5,
      validateStatus: (status) => status >= 200 && status < 500
    })
    this.cookieJar.setCookiesFromHeaders(r3.headers)

    const $3 = cheerio.load(r3.data)
    const csrfMeta = $3('meta[name="csrf-token"]').attr('content')
    if (csrfMeta) {
      this.csrfToken = csrfMeta
      return true
    }

    const currentUrl = (r3.request && (r3.request.res?.responseUrl || r3.request._currentUrl)) || ''
    if (currentUrl.includes('/login') || $3('input[name="_token"]').length > 0 || r3.status === 401) {
      this.lastError = 'Tài khoản hoặc mật khẩu không chính xác (bị điều hướng lại trang login).'
    } else {
      this.lastError = 'Không tìm thấy csrf-token trong trang admin (kiểm tra quyền hạn của tài khoản CMS).'
    }
    return false
  }

  private async loginTreeIQFlow(): Promise<boolean> {
    const loginUrl = `${this.baseUrl}/login`
    const postData = new URLSearchParams()
    postData.append('email', this.username)
    postData.append('password', this.pass)

    const r2 = await this.client.post(loginUrl, postData.toString(), {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        Cookie: this.cookieJar.getCookieHeader()
      },
      maxRedirects: 0,
      validateStatus: (status) => status >= 200 && status < 400
    })
    this.cookieJar.setCookiesFromHeaders(r2.headers)

    // If status 200 without redirect, check for error alert in HTML
    if (r2.status === 200 && r2.data && typeof r2.data === 'string') {
      const $2 = cheerio.load(r2.data)
      const errorBox = $2('.alert-danger, .invalid-feedback, .error-msg, .text-danger, .error').first().text().trim()
      if (errorBox) {
        this.lastError = `Sai tài khoản hoặc mật khẩu: ${errorBox}`
        return false
      }
    }

    // Inspect admin page to fetch CSRF token & categories
    const adminUrl = `${this.baseUrl}/admin/posts/new`
    const r3 = await this.client.get(adminUrl, {
      headers: {
        Cookie: this.cookieJar.getCookieHeader()
      },
      maxRedirects: 5,
      validateStatus: (status) => status >= 200 && status < 500
    })
    this.cookieJar.setCookiesFromHeaders(r3.headers)

    const currentUrl = (r3.request && (r3.request.res?.responseUrl || r3.request._currentUrl)) || ''
    const $3 = cheerio.load(r3.data || '')

    if (
      currentUrl.includes('/login') ||
      r3.status === 401 ||
      r3.status === 403 ||
      $3('form[action="/login"]').length > 0
    ) {
      const errMsg =
        $3('.alert-danger, .invalid-feedback, .error-msg, .text-danger').first().text().trim() ||
        'Tài khoản hoặc mật khẩu không chính xác (bị điều hướng lại trang login).'
      this.lastError = errMsg.startsWith('Sai') || errMsg.startsWith('Tài khoản') ? errMsg : `Sai tài khoản hoặc mật khẩu: ${errMsg}`
      return false
    }

    // Extract TreeIQ CSRF token from input[name="csrf_token"] or meta[name="csrf-token"]
    const tokenVal =
      $3('input[name="csrf_token"]').val() ||
      $3('input[name="_token"]').val() ||
      $3('meta[name="csrf-token"]').attr('content')

    if (tokenVal) {
      this.csrfToken = String(tokenVal)
    }

    // Extract available categories
    const cats: CMSCategory[] = []
    $3('select[name="category_id"] option').each((_, opt) => {
      const val = $3(opt).val()
      const text = $3(opt).text().trim()
      if (val && val !== '') {
        cats.push({ id: String(val), name: text })
      }
    })
    this.availableCategories = cats
    if (!this.customCategoryProvided && cats.length > 0) {
      this.categoryId = cats[0].id
    }

    if (!this.csrfToken) {
      this.lastError = 'Không tìm thấy csrf_token trong trang admin TreeIQ (kiểm tra quyền hạn tài khoản).'
      return false
    }

    return true
  }

  public buildChapterDescription(coverUrl: string, chapter: ChapterContent): string {
    return buildChapterDescription(coverUrl, chapter)
  }

  public async publishTreeIQStory(
    storyInfo: StoryInfo,
    chapters: ChapterContent[],
    onLog?: (msg: string) => void
  ): Promise<any[] | null> {
    const resolvedChapters: ChapterContent[] = []
    for (const ch of chapters) {
      resolvedChapters.push(...splitChapterByParts(ch))
    }

    if (resolvedChapters.length === 0) {
      this.lastError = 'Không có nội dung chương nào để đăng.'
      return null
    }

    if (!this.csrfToken) {
      const ok = await this.login()
      if (!ok) return null
    }

    const storyTitle =
      (storyInfo.title || '').trim().toUpperCase() ||
      formatChapterTitleTreeIQ(resolvedChapters[0].title, 1)

    const slug = generateTreeIQSlug(storyInfo.title, storyInfo.slug)
    const excerpt = buildTreeIQExcerpt(resolvedChapters, 90)
    const bodyHtml = buildTreeIQBodyHtml(resolvedChapters)
    const bodyText = buildTreeIQBodyText(resolvedChapters)

    let featuredImage = resolveFeaturedImageUrl(storyInfo.cover_image, this.baseUrl)
    if (!featuredImage && resolvedChapters[0].images && resolvedChapters[0].images.length > 0) {
      featuredImage = resolveFeaturedImageUrl(resolvedChapters[0].images[0], this.baseUrl)
    }

    const apiUrl = `${this.baseUrl}/admin/posts`
    const formData = new URLSearchParams()
    formData.append('csrf_token', this.csrfToken || '')
    formData.append('title', storyTitle)
    formData.append('slug', slug)
    formData.append('category_id', this.categoryId || '9')
    formData.append('category_ids', this.categoryId || '9')
    formData.append('status', 'PUBLISHED')
    formData.append('featured_image_url', featuredImage)
    formData.append('excerpt', excerpt)
    formData.append('body_html', bodyHtml)
    formData.append('body_text', bodyText)

    if (onLog) {
      onLog(`🚀 Đang đăng bài tổng hợp (${resolvedChapters.length} chương) lên TreeIQ: ${storyTitle}...`)
    }

    try {
      const res = await this.client.post(apiUrl, formData.toString(), {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          Cookie: this.cookieJar.getCookieHeader()
        },
        maxRedirects: 0,
        validateStatus: (status) => status >= 200 && status < 400
      })
      this.cookieJar.setCookiesFromHeaders(res.headers)

      if (res.status === 200 || res.status === 201 || res.status === 303 || res.status === 302) {
        const loc = res.headers.location || ''
        const matchId = loc.match(/\/posts\/(\d+)/)
        const postId = matchId ? matchId[1] : 'treeiq-1'
        const postUrl = `${this.baseUrl}/story/${slug}`
        const postData = {
          id: postId,
          title: storyTitle,
          slug: slug,
          url: postUrl
        }
        if (onLog) {
          onLog(`🎉 Đã đăng thành công câu chuyện lên TreeIQ: ${storyTitle} (ID: ${postId})`)
          onLog(`   👉 Link bài viết: ${postUrl}`)
        }
        return [postData]
      } else {
        const errDetail = `HTTP ${res.status}`
        this.lastError = errDetail
        if (onLog) {
          onLog(`Lỗi đăng câu chuyện lên TreeIQ: ${errDetail}`)
        }
        return null
      }
    } catch (err: any) {
      this.lastError = `Lỗi gửi request: ${err.message}`
      if (onLog) {
        onLog(`Lỗi đăng câu chuyện lên TreeIQ: ${err.message}`)
      }
      return null
    }
  }

  public async publishBlogBioStory(
    storyInfo: StoryInfo,
    chapters: ChapterContent[],
    onLog?: (msg: string) => void
  ): Promise<any[] | null> {
    const resolvedChapters: ChapterContent[] = []
    for (const ch of chapters) {
      resolvedChapters.push(...splitChapterByParts(ch))
    }

    if (resolvedChapters.length === 0) {
      this.lastError = 'Không có nội dung chương nào để đăng.'
      return null
    }

    if (!this.csrfToken) {
      const ok = await this.login()
      if (!ok) return null
    }

    const chapterSlugs: string[] = []
    const seenSlugs = new Set<string>()

    for (let idx = 0; idx < resolvedChapters.length; idx++) {
      const ch = resolvedChapters[idx]
      let baseSlug = generateSlug(ch.title)
      if (baseSlug.split('-').length <= 2 && storyInfo.slug) {
        baseSlug = `${storyInfo.slug}-${baseSlug}`
      }
      if (!baseSlug) baseSlug = `chapter-${idx + 1}`

      let slugCandidate = baseSlug
      let counter = 1
      while (seenSlugs.has(slugCandidate)) {
        slugCandidate = `${baseSlug}-${counter}`
        counter++
      }
      seenSlugs.add(slugCandidate)
      chapterSlugs.push(slugCandidate)
    }

    const createdPosts: any[] = []
    const total = resolvedChapters.length

    for (let idx = 0; idx < resolvedChapters.length; idx++) {
      const ch = resolvedChapters[idx]
      const currentSlug = chapterSlugs[idx]
      const prevSlug = idx > 0 ? chapterSlugs[idx - 1] : null
      const nextSlug = idx < total - 1 ? chapterSlugs[idx + 1] : null

      const chapterFeaturedImage =
        (ch.images && ch.images.length > 0 && isImageUrl(ch.images[0]) ? ch.images[0].trim() : '') ||
        ch.content_elements?.find(([t, v]) => (t === 'image' || isImageUrl(v)) && isImageUrl(v))?.[1]?.trim() ||
        storyInfo.cover_image?.trim() ||
        ''

      if (!storyInfo.cover_image && chapterFeaturedImage) {
        storyInfo.cover_image = chapterFeaturedImage
      }

      const coverUrlForDesc = chapterFeaturedImage || storyInfo.cover_image || ''
      const chDesc = this.buildChapterDescription(coverUrlForDesc, ch)

      const apiUrl = `${this.baseUrl}/admin/api/v1/posts`
      const payload = {
        title: ch.title,
        slug: currentSlug,
        image: coverUrlForDesc,
        description: chDesc,
        series_id: null,
        prev_chapter: prevSlug,
        next_chapter: nextSlug,
        is_active: true,
        is_home: true,
        is_top: idx === 0
      }

      try {
        const res = await this.client.post(apiUrl, payload, {
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-TOKEN': this.csrfToken,
            Cookie: this.cookieJar.getCookieHeader()
          }
        })
        this.cookieJar.setCookiesFromHeaders(res.headers)

        if (res.status === 200 || res.status === 201) {
          const postData = res.data?.data || {}
          createdPosts.push(postData)
          if (onLog) {
            onLog(`[${idx + 1}/${total}] Đã đăng chapter: ${ch.title} (ID: ${postData.id || 'N/A'})`)
          }
        }
      } catch (err: any) {
        if (onLog) {
          onLog(`[${idx + 1}/${total}] Lỗi đăng '${ch.title}': ${err.message}`)
        }
      }
    }

    return createdPosts.length > 0 ? createdPosts : null
  }

  public async publishStory(
    storyInfo: StoryInfo,
    chapters: ChapterContent[],
    onLog?: (msg: string) => void
  ): Promise<any[] | null> {
    if (this.cmsType === 'treeiq') {
      return this.publishTreeIQStory(storyInfo, chapters, onLog)
    } else {
      return this.publishBlogBioStory(storyInfo, chapters, onLog)
    }
  }
}

