import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'
import {
  SimpleCookieJar,
  CMSPublisher,
  StoryInfo,
  buildChapterDescription,
  markdownToHtmlFormatting,
  isImageUrl,
  formatChapterTitleTreeIQ,
  generateTreeIQSlug,
  buildTreeIQExcerpt,
  buildTreeIQBodyHtml,
  buildTreeIQBodyText,
  resolveFeaturedImageUrl
} from '../src/main/services/publisher'
import { ChapterContent } from '../src/main/services/translator'

vi.mock('axios')
const mockedAxios = vi.mocked(axios, true)

describe('CMS Publisher & Cookie Jar Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ================= 1. HAPPY PATHS =================
  describe('Happy Paths', () => {
    it('SimpleCookieJar correctly parses, stores, and formats cookies', () => {
      const jar = new SimpleCookieJar()
      jar.setCookiesFromHeaders({
        'set-cookie': [
          'XSRF-TOKEN=token123; expires=Wed, 21-Oct-2026; path=/',
          'vmteasyazfejiio_session=sess456; path=/; HttpOnly'
        ]
      })

      expect(jar.get('XSRF-TOKEN')).toBe('token123')
      expect(jar.get('vmteasyazfejiio_session')).toBe('sess456')
      expect(jar.getCookieHeader()).toBe('XSRF-TOKEN=token123; vmteasyazfejiio_session=sess456')

      // Updating a cookie should overwrite existing
      jar.setCookiesFromHeaders({
        'set-cookie': ['vmteasyazfejiio_session=new_sess789; path=/; HttpOnly']
      })
      expect(jar.get('vmteasyazfejiio_session')).toBe('new_sess789')
      expect(jar.size()).toBe(2)
    })

    it('CMSPublisher logs in successfully when credentials and tokens match', async () => {
      const mockClient = {
        get: vi.fn(),
        post: vi.fn()
      }
      mockedAxios.create.mockReturnValue(mockClient as any)

      // Step 1: GET /login returns page with _token
      mockClient.get.mockImplementation(async (url: string) => {
        if (url.endsWith('/login')) {
          return {
            status: 200,
            headers: {
              'set-cookie': ['XSRF-TOKEN=init-token; path=/', 'session=init-session; path=/']
            },
            data: '<html><body><input name="_token" value="test-csrf-login-token" /></body></html>'
          }
        }
        if (url.endsWith('/admin/posts/new')) {
          return {
            status: 200,
            headers: {},
            data: '<html><head><meta name="csrf-token" content="admin-meta-csrf-999" /></head></html>'
          }
        }
        return { status: 404, headers: {}, data: '' }
      })

      // Step 2: POST /login returns 302 redirect with new auth session cookie
      mockClient.post.mockResolvedValueOnce({
        status: 302,
        headers: {
          location: 'https://example.com/admin/dashboard',
          'set-cookie': ['session=auth-session-active; path=/', 'remember_token=rem123; path=/']
        },
        data: ''
      })

      const publisher = new CMSPublisher('https://example.com/', 'admin', 'password123')
      const success = await publisher.login()

      expect(success).toBe(true)
      expect(publisher.lastError).toBe('')
      expect(mockClient.get).toHaveBeenCalledWith('https://example.com/login', expect.anything())
      expect(mockClient.post).toHaveBeenCalledWith(
        'https://example.com/login',
        expect.stringContaining('_token=test-csrf-login-token'),
        expect.objectContaining({ maxRedirects: 0 })
      )
      expect(mockClient.get).toHaveBeenCalledWith(
        'https://example.com/admin/posts/new',
        expect.objectContaining({
          headers: expect.objectContaining({
            Cookie: expect.stringContaining('auth-session-active')
          })
        })
      )
    })

    it('publishes story chapters with correct headers and payload format', async () => {
      const mockClient = {
        get: vi.fn(),
        post: vi.fn()
      }
      mockedAxios.create.mockReturnValue(mockClient as any)

      // Mock login flow
      mockClient.get.mockImplementation(async (url: string) => {
        if (url.endsWith('/login')) {
          return {
            status: 200,
            headers: { 'set-cookie': ['session=test-sess'] },
            data: '<input name="_token" value="tok" />'
          }
        }
        return {
          status: 200,
          headers: {},
          data: '<meta name="csrf-token" content="csrf-publish-token" />'
        }
      })
      mockClient.post.mockResolvedValueOnce({
        status: 302,
        headers: { 'set-cookie': ['session=authed-sess'] },
        data: ''
      })

      // Mock chapter create API post
      mockClient.post.mockResolvedValue({
        status: 200,
        headers: {},
        data: { data: { id: 101, title: 'Chương 1' } }
      })

      const publisher = new CMSPublisher('https://example.com', 'admin', 'password')
      const storyInfo: StoryInfo = {
        title: 'Đấu Phá Khung Thương',
        slug: 'dau-pha-khung-thuong',
        cover_image: 'https://example.com/cover.jpg'
      }
      const chapters: ChapterContent[] = [
        {
          chapter_number: 1,
          title: 'Chương 1: Khởi đầu',
          url: 'https://example.com/ch-1',
          content_elements: [
            ['heading', 'Tiêu đề phụ'],
            ['text', 'Đoạn văn thứ nhất.'],
            ['quote', 'Lời thoại nhân vật.']
          ]
        }
      ]

      const logs: string[] = []
      const res = await publisher.publishStory(storyInfo, chapters, (msg) => logs.push(msg))

      expect(res).toBeDefined()
      expect(res).toHaveLength(1)
      expect(res![0].id).toBe(101)
      expect(logs.some((l) => l.includes('Chương 1'))).toBe(true)

      // Verify POST headers included X-CSRF-TOKEN and Cookie
      expect(mockClient.post).toHaveBeenCalledWith(
        'https://example.com/admin/api/v1/posts',
        expect.objectContaining({
          title: 'Chương 1: Khởi đầu',
          image: 'https://example.com/cover.jpg'
        }),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-CSRF-TOKEN': 'csrf-publish-token',
            Cookie: expect.stringContaining('authed-sess')
          })
        })
      )
    })

    it('publishes story chapters automatically filling image field from chapter image when storyInfo.cover_image is empty', async () => {
      const mockClient = {
        get: vi.fn(),
        post: vi.fn()
      }
      mockedAxios.create.mockReturnValue(mockClient as any)

      mockClient.get.mockImplementation(async (url: string) => {
        if (url.endsWith('/login')) {
          return { status: 200, headers: { 'set-cookie': ['session=test-sess'] }, data: '<input name="_token" value="tok" />' }
        }
        return { status: 200, headers: {}, data: '<meta name="csrf-token" content="csrf-tok" />' }
      })
      mockClient.post.mockResolvedValueOnce({
        status: 302,
        headers: { 'set-cookie': ['session=authed-sess'] },
        data: ''
      })
      mockClient.post.mockResolvedValue({
        status: 200,
        headers: {},
        data: { data: { id: 102, title: 'Chapter 1' } }
      })

      const publisher = new CMSPublisher('https://example.com', 'admin', 'password')
      const storyInfo: StoryInfo = {
        title: 'Story Without Initial Cover',
        slug: 'story-no-cover'
      }
      const chapters: ChapterContent[] = [
        {
          chapter_number: 1,
          title: 'Chapter 1',
          images: ['https://cdn.treeiq.biz/site_101/2026/10/chapter1-featured.jpg'],
          content_elements: [
            ['text', 'The ring arrived on a Tuesday.']
          ]
        }
      ]

      const res = await publisher.publishStory(storyInfo, chapters)
      expect(res).toBeDefined()
      expect(res).toHaveLength(1)

      expect(mockClient.post).toHaveBeenCalledWith(
        'https://example.com/admin/api/v1/posts',
        expect.objectContaining({
          title: 'Chapter 1',
          image: 'https://cdn.treeiq.biz/site_101/2026/10/chapter1-featured.jpg'
        }),
        expect.anything()
      )
    })

    it('TreeIQ CMS: logs in and publishes chapters to vmstoryab.teasy.live successfully', async () => {
      const mockClient = {
        get: vi.fn(),
        post: vi.fn()
      }
      mockedAxios.create.mockReturnValue(mockClient as any)

      mockClient.get.mockImplementation(async (url: string) => {
        if (url.endsWith('/login')) {
          return {
            status: 200,
            headers: {},
            data: '<form action="/login"><input name="email"><input name="password"></form>'
          }
        }
        if (url.endsWith('/admin/posts/new')) {
          return {
            status: 200,
            headers: {},
            data: `
              <form action="/admin/posts">
                <input name="csrf_token" type="hidden" value="treeiq-csrf-token-123" />
                <select name="category_id">
                  <option value="9" selected>Drama Us</option>
                  <option value="10">Romance</option>
                </select>
              </form>
            `
          }
        }
        return { status: 404, headers: {}, data: '' }
      })

      mockClient.post.mockImplementation(async (url: string) => {
        if (url.endsWith('/login')) {
          return {
            status: 303,
            headers: {
              location: '/admin',
              'set-cookie': ['treeiq_session=sess-treeiq-999; path=/; HttpOnly; Secure']
            },
            data: ''
          }
        }
        if (url.endsWith('/admin/posts')) {
          return {
            status: 303,
            headers: {
              location: '/admin/posts/802',
              'set-cookie': ['treeiq_session=sess-treeiq-999; path=/; HttpOnly; Secure']
            },
            data: ''
          }
        }
        return { status: 404, headers: {}, data: '' }
      })

      const publisher = new CMSPublisher('https://vmstoryab.teasy.live', 'vinhmai@teasy.live', 'Vnpt@@123456')
      expect(publisher.cmsType).toBe('treeiq')

      const loginOk = await publisher.login()
      expect(loginOk).toBe(true)
      expect(publisher.availableCategories).toEqual([
        { id: '9', name: 'Drama Us' },
        { id: '10', name: 'Romance' }
      ])
      expect(publisher.categoryId).toBe('9')

      const storyInfo: StoryInfo = {
        title: 'The Billionaire Secret',
        slug: 'the-billionaire-secret',
        cover_image: 'https://cdn.treeiq.biz/site_547/cover.webp'
      }
      const chapters: ChapterContent[] = [
        {
          chapter_number: 1,
          title: 'Chapter 1: The Beginning',
          content_elements: [
            ['heading', 'Part 1'],
            ['text', 'Luca sat silently in the room.'],
            ['image', 'https://cdn.treeiq.biz/site_547/img1.webp']
          ]
        }
      ]

      const results = await publisher.publishStory(storyInfo, chapters)
      expect(results).toBeDefined()
      expect(results).toHaveLength(1)
      expect(results![0]).toEqual(
        expect.objectContaining({
          id: '802',
          title: 'THE BILLIONAIRE SECRET'
        })
      )

      const postCalls = mockClient.post.mock.calls.filter((c: any) => c[0].endsWith('/admin/posts'))
      expect(postCalls.length).toBe(1)
      const sentBody = postCalls[0][1]
      expect(sentBody).toContain('csrf_token=treeiq-csrf-token-123')
      expect(sentBody).toContain('category_id=9')
      expect(sentBody).toContain('status=PUBLISHED')
      expect(sentBody).toContain('featured_image_url=https%3A%2F%2Fcdn.treeiq.biz%2Fsite_547%2Fcover.webp')
      expect(sentBody).toContain('body_html=')
      expect(sentBody).toContain('body_text=')
    })

    it('isImageUrl detects image URLs with various extensions and query strings', () => {
      expect(isImageUrl('https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg')).toBe(true)
      expect(isImageUrl('https://example.com/photo.png?w=600&h=400')).toBe(true)
      expect(isImageUrl('https://example.com/picture.webp')).toBe(true)
      expect(isImageUrl('https://example.com/vector.svg')).toBe(true)
      expect(isImageUrl('https://example.com/chapter-1')).toBe(false)
      expect(isImageUrl('The ring arrived on a Tuesday.')).toBe(false)
      expect(isImageUrl('')).toBe(false)
    })

    it('markdownToHtmlFormatting converts markdown styles to HTML tags', () => {
      expect(markdownToHtmlFormatting('**đậm**')).toBe('<strong>đậm</strong>')
      expect(markdownToHtmlFormatting('*nghiêng*')).toBe('<em>nghiêng</em>')
      expect(markdownToHtmlFormatting('~~gạch ngang~~')).toBe('<del>gạch ngang</del>')
      expect(markdownToHtmlFormatting('***đậm và nghiêng***')).toBe('<strong><em>đậm và nghiêng</em></strong>')
    })

    it('buildChapterDescription renders images as <img> tags instead of plain text URLs', () => {
      const chapter: ChapterContent = {
        chapter_number: 1,
        title: 'Chương 1',
        content_elements: [
          ['image', 'https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg'],
          ['text', 'The ring arrived on a Tuesday.'],
          ['text', 'Nobody sent Mara anything. She was a housekeeper.']
        ]
      }
      const html = buildChapterDescription('', chapter)
      expect(html).toContain('<p><img src="https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg" alt=""></p>')
      expect(html).not.toContain('<p>https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg</p>')
      expect(html).toContain('<p>The ring arrived on a Tuesday.</p>')
    })

    it('buildChapterDescription converts raw image URLs categorized as text to <img> tags', () => {
      const chapter: ChapterContent = {
        chapter_number: 1,
        title: 'Chương 1',
        content_elements: [
          ['text', 'https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg'],
          ['text', 'The ring arrived on a Tuesday.']
        ]
      }
      const html = buildChapterDescription('', chapter)
      expect(html).toContain('<p><img src="https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg" alt=""></p>')
      expect(html).not.toContain('<p>https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg</p>')
    })

    it('buildChapterDescription converts markdown images ![alt](url) to <img> tags', () => {
      const chapter: ChapterContent = {
        chapter_number: 1,
        title: 'Chương 1',
        content_elements: [
          ['text', '![Ảnh minh họa](https://cdn.treeiq.biz/sample.png)'],
          ['text', 'Nội dung tiếp theo.']
        ]
      }
      const html = buildChapterDescription('', chapter)
      expect(html).toContain('<p><img src="https://cdn.treeiq.biz/sample.png" alt="Ảnh minh họa"></p>')
    })

    it('formatChapterTitleTreeIQ converts various chapter title formats into CHAPTER X — TITLE', () => {
      expect(formatChapterTitleTreeIQ('Chapter 1 - The Shattered Past', 1)).toBe('CHAPTER 1 — THE SHATTERED PAST')
      expect(formatChapterTitleTreeIQ('CHAPTER 2 — THE BOY WHO SHOULD NOT EXIST', 2)).toBe('CHAPTER 2 — THE BOY WHO SHOULD NOT EXIST')
      expect(formatChapterTitleTreeIQ('Chapter 3: The Secret Beneath', 3)).toBe('CHAPTER 3 — THE SECRET BENEATH')
      expect(formatChapterTitleTreeIQ('4. The Final Stand', 4)).toBe('CHAPTER 4 — THE FINAL STAND')
      expect(formatChapterTitleTreeIQ('Epilogue', 5)).toBe('CHAPTER 5 — EPILOGUE')
    })

    it('generateTreeIQSlug appends a 6-character random suffix to ensure uniqueness', () => {
      const slug1 = generateTreeIQSlug('The Boy The Kingdom Feared')
      const slug2 = generateTreeIQSlug('The Boy The Kingdom Feared')
      expect(slug1).toMatch(/^the-boy-the-kingdom-feared-[a-z0-9]{6}$/)
      expect(slug2).toMatch(/^the-boy-the-kingdom-feared-[a-z0-9]{6}$/)
      expect(slug1).not.toBe(slug2)
    })

    it('buildTreeIQBodyHtml aggregates all chapters into a single structured HTML document', () => {
      const chs: ChapterContent[] = [
        {
          chapter_number: 1,
          title: 'Chapter 1 - The Beginning',
          paragraphs: ['The bells rang at midnight.', 'A boy entered the throne room.']
        },
        {
          chapter_number: 2,
          title: 'Chapter 2 - The Secret',
          paragraphs: ['Take him away! the King yelled.']
        }
      ]
      const html = buildTreeIQBodyHtml(chs)
      expect(html).toContain('<h2>CHAPTER 1 — THE BEGINNING</h2>')
      expect(html).toContain('<p>The bells rang at midnight.</p>')
      expect(html).toContain('<h2>CHAPTER 2 — THE SECRET</h2>')
      expect(html).toContain('<p>Take him away! the King yelled.</p>')
    })

    it('buildTreeIQBodyHtml and buildChapterDescription strictly insert only 1 image per chapter even if multiple images exist', () => {
      const chapterWithMultipleImages: ChapterContent = {
        chapter_number: 1,
        title: 'Chapter 1 - Test Single Image',
        paragraphs: ['Paragraph 1', 'Paragraph 2'],
        images: ['https://example.com/img1.webp', 'https://example.com/img2.webp'],
        content_elements: [
          ['image', 'https://example.com/img1.webp'],
          ['text', '![Alt](https://example.com/img3.webp) Some text'],
          ['image', 'https://example.com/img4.webp']
        ]
      }

      const htmlTreeIQ = buildTreeIQBodyHtml([chapterWithMultipleImages])
      const imgMatchesTreeIQ = htmlTreeIQ.match(/<img\s/g) || []
      expect(imgMatchesTreeIQ.length).toBe(1)
      expect(htmlTreeIQ).toContain('https://example.com/img1.webp')
      expect(htmlTreeIQ).not.toContain('https://example.com/img3.webp')
      expect(htmlTreeIQ).not.toContain('https://example.com/img4.webp')

      const htmlBlogBio = buildChapterDescription('https://example.com/cover.webp', chapterWithMultipleImages)
      const imgMatchesBlogBio = htmlBlogBio.match(/<img\s/g) || []
      expect(imgMatchesBlogBio.length).toBe(1)
      expect(htmlBlogBio).toContain('https://example.com/cover.webp')
    })

    it('resolveFeaturedImageUrl only accepts absolute http(s) URLs and rejects invalid/relative paths', () => {
      expect(resolveFeaturedImageUrl('https://example.com/cover.webp')).toBe('https://example.com/cover.webp')
      expect(resolveFeaturedImageUrl('/images/cover.jpg', 'https://example.com')).toBe('https://example.com/images/cover.jpg')
      expect(resolveFeaturedImageUrl('local-file.jpg')).toBe('')
      expect(resolveFeaturedImageUrl('')).toBe('')
      expect(resolveFeaturedImageUrl(undefined)).toBe('')
    })

    it('TreeIQ publishes 1 combined post for multi-chapter stories, whereas BlogBio publishes per-chapter', async () => {
      const mockClient = {
        get: vi.fn().mockImplementation(async (url: string) => {
          if (url.endsWith('/login')) return { status: 200, headers: {}, data: '<form action="/login"></form>' }
          return { status: 200, headers: {}, data: '<input name="csrf_token" value="tree-csrf" />' }
        }),
        post: vi.fn().mockImplementation(async (url: string) => {
          if (url.endsWith('/login')) return { status: 303, headers: { location: '/admin' }, data: '' }
          return { status: 303, headers: { location: '/admin/posts/999' }, data: '' }
        })
      }
      mockedAxios.create.mockReturnValue(mockClient as any)

      const publisherTreeIQ = new CMSPublisher('https://vmstoryab.teasy.live', 'vinhmai@teasy.live', 'pass')
      const multiChapters: ChapterContent[] = [
        { chapter_number: 1, title: 'Chapter 1', paragraphs: ['Para 1'] },
        { chapter_number: 2, title: 'Chapter 2', paragraphs: ['Para 2'] }
      ]

      const results = await publisherTreeIQ.publishStory({ title: 'Full Story Title', slug: 'full-story' }, multiChapters)
      expect(results).toHaveLength(1)
      expect(results![0].title).toBe('FULL STORY TITLE')

      // Verify that TreeIQ only called /admin/posts once!
      const postsCalls = mockClient.post.mock.calls.filter((c: any) => c[0].endsWith('/admin/posts'))
      expect(postsCalls).toHaveLength(1)
    })
  })

  // ================= 2. EDGE CASES =================
  describe('Edge Cases', () => {
    it('buildChapterDescription avoids duplicating coverUrl when first element has identical image URL', () => {
      const cover = 'https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg'
      const chapter: ChapterContent = {
        chapter_number: 1,
        title: 'Chương 1',
        content_elements: [
          ['image', cover],
          ['text', 'The ring arrived on a Tuesday.']
        ]
      }
      const html = buildChapterDescription(cover, chapter)
      const count = (html.match(new RegExp('https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg', 'g')) || []).length
      expect(count).toBe(1)
    })

    it('handles URLs with trailing slashes and trims credentials properly', () => {
      const mockClient = { get: vi.fn(), post: vi.fn() }
      mockedAxios.create.mockReturnValue(mockClient as any)

      const publisher = new CMSPublisher('https://vmteasyaz.feji.io///', '  admin  ', '  pass123 ')
      expect((publisher as any).baseUrl).toBe('https://vmteasyaz.feji.io')
      expect((publisher as any).username).toBe('admin')
      expect((publisher as any).pass).toBe('pass123')
    })

    it('handles single string or null/undefined in set-cookie headers', () => {
      const jar = new SimpleCookieJar()
      jar.setCookiesFromHeaders(undefined)
      expect(jar.size()).toBe(0)

      jar.setCookiesFromHeaders({ 'set-cookie': 'simple_cookie=value123; path=/' as any })
      expect(jar.get('simple_cookie')).toBe('value123')

      jar.clear()
      expect(jar.size()).toBe(0)
    })

    it('returns null and appropriate error when no chapter content is provided', async () => {
      const publisher = new CMSPublisher('https://example.com', 'admin', 'password')
      const res = await publisher.publishStory(
        { title: 'T', slug: 't' },
        []
      )
      expect(res).toBeNull()
      expect(publisher.lastError).toContain('Không có nội dung chương')
    })

    it('generates unique slugs for chapters even when duplicate titles exist', async () => {
      const mockClient = { get: vi.fn(), post: vi.fn() }
      mockedAxios.create.mockReturnValue(mockClient as any)

      mockClient.get.mockImplementation(async (url: string) => {
        if (url.endsWith('/login')) {
          return { status: 200, headers: {}, data: '<input name="_token" value="tok" />' }
        }
        return { status: 200, headers: {}, data: '<meta name="csrf-token" content="c-token" />' }
      })
      mockClient.post.mockResolvedValue({ status: 200, data: { data: { id: 1 } } })

      const publisher = new CMSPublisher('https://example.com', 'admin', 'pass')
      const chapters: ChapterContent[] = [
        { chapter_number: 1, title: 'Chương 1', url: '', content_elements: [['text', 'A']] },
        { chapter_number: 2, title: 'Chương 1', url: '', content_elements: [['text', 'B']] }
      ]

      await publisher.publishStory({ title: 'Test', slug: 'test' }, chapters)

      const calls = mockClient.post.mock.calls.filter((c: any) => c[0].endsWith('/posts'))
      expect(calls.length).toBe(2)
      const slug1 = calls[0][1].slug
      const slug2 = calls[1][1].slug
      expect(slug1).not.toBe(slug2)
    })

    it('TreeIQ CMS: supports custom category_id option and trims parameters', async () => {
      const mockClient = { get: vi.fn(), post: vi.fn() }
      mockedAxios.create.mockReturnValue(mockClient as any)

      mockClient.get.mockImplementation(async (url: string) => {
        if (url.endsWith('/login')) {
          return { status: 200, headers: {}, data: '<form action="/login"><input name="email"></form>' }
        }
        return {
          status: 200,
          headers: {},
          data: '<input name="csrf_token" value="tok99" /><select name="category_id"><option value="15">Horror</option></select>'
        }
      })
      mockClient.post.mockResolvedValue({ status: 303, headers: { location: '/admin/posts/888' }, data: '' })

      const publisher = new CMSPublisher('https://vmstoryab.teasy.live/', 'user@teasy.live', 'pass', {
        categoryId: '25'
      })
      expect(publisher.categoryId).toBe('25')
      await publisher.login()
      expect(publisher.categoryId).toBe('25')

      await publisher.publishStory(
        { title: 'Test Story', slug: 'test' },
        [{ chapter_number: 1, title: 'Ch 1', content_elements: [['text', 'Hello']] }]
      )

      const postCall = mockClient.post.mock.calls.find((c: any) => c[0].endsWith('/admin/posts'))
      expect(postCall[1]).toContain('category_id=25')
    })
  })

  // ================= 3. ERROR HANDLING =================
  describe('Error Handling', () => {
    it('fails gracefully when login page does not contain _token', async () => {
      const mockClient = {
        get: vi.fn().mockResolvedValueOnce({
          status: 200,
          headers: {},
          data: '<html><body>Login page without token form</body></html>'
        }),
        post: vi.fn()
      }
      mockedAxios.create.mockReturnValue(mockClient as any)

      const publisher = new CMSPublisher('https://example.com', 'admin', 'wrong')
      const ok = await publisher.login()

      expect(ok).toBe(false)
      expect(publisher.lastError).toContain('Không tìm thấy _token')
    })

    it('handles 401 / redirect back to login when credentials are bad', async () => {
      const mockClient = {
        get: vi.fn(),
        post: vi.fn()
      }
      mockedAxios.create.mockReturnValue(mockClient as any)

      mockClient.get.mockImplementation(async (url: string) => {
        if (url.endsWith('/login')) {
          return { status: 200, headers: {}, data: '<input name="_token" value="tok" />' }
        }
        if (url.endsWith('/admin/posts/new')) {
          // Redirected back to login
          return {
            status: 200,
            headers: {},
            data: '<html><body><input name="_token" value="tok" /><div class="alert alert-danger">These credentials do not match our records.</div></body></html>',
            request: { res: { responseUrl: 'https://example.com/login' } }
          }
        }
        return { status: 404, headers: {}, data: '' }
      })

      mockClient.post.mockResolvedValueOnce({
        status: 302,
        headers: { location: 'https://example.com/login' },
        data: ''
      })

      const publisher = new CMSPublisher('https://example.com', 'admin', 'badpass')
      const ok = await publisher.login()

      expect(ok).toBe(false)
      expect(publisher.lastError).toContain('Tài khoản hoặc mật khẩu không chính xác')
    })

    it('handles network exceptions during login gracefully', async () => {
      const mockClient = {
        get: vi.fn().mockRejectedValueOnce(new Error('getaddrinfo ENOTFOUND invalid-domain.xyz')),
        post: vi.fn()
      }
      mockedAxios.create.mockReturnValue(mockClient as any)

      const publisher = new CMSPublisher('https://invalid-domain.xyz', 'admin', 'pass')
      const ok = await publisher.login()

      expect(ok).toBe(false)
      expect(publisher.lastError).toContain('Lỗi kết nối CMS')
    })

    it('TreeIQ CMS: handles login authentication failure when redirected back to login with error', async () => {
      const mockClient = {
        get: vi.fn().mockImplementation(async (url: string) => {
          if (url.endsWith('/login')) {
            return { status: 200, headers: {}, data: '<form action="/login"><input name="email"></form>' }
          }
          if (url.endsWith('/admin/posts/new')) {
            return {
              status: 200,
              headers: {},
              data: '<html><body><form action="/login"><div class="alert alert-danger">Tài khoản hoặc mật khẩu không chính xác</div></form></body></html>',
              request: { res: { responseUrl: 'https://vmstoryab.teasy.live/login' } }
            }
          }
          return { status: 404, headers: {}, data: '' }
        }),
        post: vi.fn().mockResolvedValue({
          status: 200,
          headers: {},
          data: '<div class="alert alert-danger">Sai mật khẩu</div>'
        })
      }
      mockedAxios.create.mockReturnValue(mockClient as any)

      const publisher = new CMSPublisher('https://vmstoryab.teasy.live', 'vinhmai@teasy.live', 'wrongpass')
      const ok = await publisher.login()
      expect(ok).toBe(false)
      expect(publisher.lastError).toContain('Sai tài khoản hoặc mật khẩu')
    })

    it('TreeIQ CMS: handles post creation failure and logs error message', async () => {
      const mockClient = {
        get: vi.fn().mockImplementation(async (url: string) => {
          if (url.endsWith('/login')) return { status: 200, headers: {}, data: '<form action="/login"></form>' }
          return { status: 200, headers: {}, data: '<input name="csrf_token" value="tok" />' }
        }),
        post: vi.fn().mockImplementation(async (url: string) => {
          if (url.endsWith('/login')) return { status: 303, headers: { location: '/admin' }, data: '' }
          return { status: 500, headers: {}, data: 'Internal Server Error' }
        })
      }
      mockedAxios.create.mockReturnValue(mockClient as any)

      const logs: string[] = []
      const publisher = new CMSPublisher('https://vmstoryab.teasy.live', 'u', 'p')
      const res = await publisher.publishStory(
        { title: 'T', slug: 't' },
        [{ chapter_number: 1, title: 'C1', content_elements: [['text', 'Txt']] }],
        (msg) => logs.push(msg)
      )

      expect(res).toBeNull()
      expect(logs.some((l) => l.includes('Lỗi đăng') || l.includes('500'))).toBe(true)
    })
  })
})

