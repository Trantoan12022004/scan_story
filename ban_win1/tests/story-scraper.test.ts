import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import {
  detectParser,
  UniversalParser,
  AHCMSParser,
  TreeIQParser,
  extractCoverImage,
  fixMojibake,
  sanitizeFolderName,
  saveChapter,
  saveFullStory,
  StoryScraperEngine,
  ChapterContent,
  StoryInfo
} from '../src/main/services/story-scraper'

describe('Story Scraper Service & Parsers', () => {
  let tempDir: string

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'banwin-scraper-test-'))
  })

  afterEach(() => {
    try {
      fs.rmSync(tempDir, { recursive: true, force: true })
    } catch {}
  })

  // ================= 1. HAPPY PATHS =================
  describe('Happy Paths', () => {
    it('detects specialized parsers and falls back to UniversalParser', () => {
      expect(detectParser('https://sad.treeiq.biz/blog/test-story')).toBeInstanceOf(TreeIQParser)
      expect(detectParser('https://whisper.fast2tricks.com/story-123')).toBeInstanceOf(AHCMSParser)
      expect(detectParser('https://truyenfull.vn/dau-pha-thuong-khung/')).toBeInstanceOf(UniversalParser)
      expect(detectParser('https://example.com/novel/chapter-1')).toBeInstanceOf(UniversalParser)
    })

    it('extracts story info and chapters correctly using UniversalParser', () => {
      const parser = new UniversalParser()
      const sampleHtml = `
        <!DOCTYPE html>
        <html>
        <head>
          <title>Legend of the Dragon | ReadingSite</title>
          <meta property="og:title" content="Legend of the Dragon | ReadingSite" />
          <meta property="og:image" content="https://example.com/cover.jpg" />
        </head>
        <body>
          <h1>Legend of the Dragon</h1>
          <div class="chapter-list">
            <a href="/story/chapter-1">Chapter 1: The Beginning</a>
            <a href="/story/chapter-2">Chapter 2: The Fire</a>
            <a href="/story/chapter-3">Chapter 3: The Flight</a>
          </div>
        </body>
        </html>
      `
      const info = parser.getStoryInfo(sampleHtml, 'https://example.com/story/chapter-1')
      expect(info.title).toBe('Legend of the Dragon')
      expect(info.total_chapters).toBe(3)
      expect(info.cover_image).toBe('https://example.com/cover.jpg')
      expect(info.is_single_page).toBe(false)
    })

    it('extracts cover_image correctly in TreeIQParser from og:image or page', () => {
      const parser = new TreeIQParser()
      const html = `
        <!DOCTYPE html>
        <html>
        <head>
          <meta property="og:image" content="https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg" />
        </head>
        <body>
          <h1 class="v5-title">The Ring Arrived On A Tuesday</h1>
          <ol id="chapter-toc-list-desktop">
            <li><a href="/chapter-1">Chapter 1</a></li>
            <li><a href="/chapter-2">Chapter 2</a></li>
          </ol>
        </body>
        </html>
      `
      const info = parser.getStoryInfo(html, 'https://sad.treeiq.biz/blog/the-ring')
      expect(info.cover_image).toBe('https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg')
      expect(info.total_chapters).toBe(2)
    })

    it('extracts cover_image correctly in AHCMSParser', () => {
      const parser = new AHCMSParser()
      const html = `
        <!DOCTYPE html>
        <html>
        <head>
          <meta property="og:title" content="Whisper of the Wind" />
          <meta property="og:image" content="/uploads/whisper-cover.jpg" />
        </head>
        <body>
          <h1 class="pst-title">Whisper of the Wind</h1>
          <ul class="ql-table"><li><a href="/chapter-1">Ch 1</a></li></ul>
        </body>
        </html>
      `
      const info = parser.getStoryInfo(html, 'https://whisper.fast2tricks.com/story-123')
      expect(info.cover_image).toBe('https://whisper.fast2tricks.com/uploads/whisper-cover.jpg')
    })


    it('parses chapter elements (heading, text, quote, images) and strips ads/scripts', () => {
      const parser = new UniversalParser()
      const chapterHtml = `
        <!DOCTYPE html>
        <html>
        <head><title>Chapter 1: Awaken</title></head>
        <body>
          <h1 class="title">Chapter 1: Awaken</h1>
          <div class="entry-content">
            <script>console.log("ad code")</script>
            <div class="ads-banner">Buy crypto now!</div>
            <p><strong>First line</strong> of the great novel.</p>
            <h2>The Secret Gate</h2>
            <p>The gate creaked open slowly in the dark.</p>
            <blockquote>An old prophecy whispered in the wind.</blockquote>
            <img src="https://example.com/images/dragon.png" alt="Dragon" />
            <div class="social-share">Share on Facebook</div>
          </div>
        </body>
        </html>
      `
      const chapter = parser.parseChapter(chapterHtml, 1)
      expect(chapter.chapter_number).toBe(1)
      expect(chapter.title).toBe('Chapter 1: Awaken')
      expect(chapter.paragraphs.length).toBeGreaterThanOrEqual(3)
      expect(chapter.images).toContain('https://example.com/images/dragon.png')

      const elementTypes = chapter.content_elements.map(([type]) => type)
      expect(elementTypes).toContain('heading')
      expect(elementTypes).toContain('text')
      expect(elementTypes).toContain('quote')
      expect(elementTypes).toContain('image')
    })

    it('saves chapter files (title.md and content.md) into organized directories', () => {
      const chapter: ChapterContent = {
        chapter_number: 1,
        title: 'Chương 1: Trọng Sinh',
        paragraphs: ['Dòng đầu tiên.', 'Dòng thứ hai.'],
        images: ['https://example.com/1.jpg'],
        content_elements: [
          ['heading', 'Chương 1: Trọng Sinh'],
          ['text', 'Dòng đầu tiên.'],
          ['quote', 'Lời trích dẫn quan trọng.'],
          ['text', 'Dòng thứ hai.']
        ]
      }

      const dirName = saveChapter(chapter, tempDir)
      expect(dirName).toBe('chapter_01')

      const titleFile = path.join(tempDir, 'chapter_01', 'title.md')
      const contentFile = path.join(tempDir, 'chapter_01', 'content.md')

      expect(fs.existsSync(titleFile)).toBe(true)
      expect(fs.existsSync(contentFile)).toBe(true)

      const titleContent = fs.readFileSync(titleFile, 'utf-8').trim()
      const bodyContent = fs.readFileSync(contentFile, 'utf-8').trim()

      expect(titleContent).toBe('Chương 1: Trọng Sinh')
      expect(bodyContent).toContain('## Chương 1: Trọng Sinh')
      expect(bodyContent).toContain('Dòng đầu tiên.')
      expect(bodyContent).toContain('> Lời trích dẫn quan trọng.')
    })

    it('saves full_story.md combining all chapters with metadata header', () => {
      const chapters: ChapterContent[] = [
        {
          chapter_number: 1,
          title: 'Chapter 1',
          paragraphs: ['Text 1'],
          content_elements: [['text', 'Text 1']]
        },
        {
          chapter_number: 2,
          title: 'Chapter 2',
          paragraphs: ['Text 2'],
          content_elements: [['text', 'Text 2']]
        }
      ]

      const storyInfo: StoryInfo = {
        title: 'My Great Adventure',
        slug: 'my-great-adventure',
        base_url: 'https://example.com/adventure',
        total_chapters: 2
      }

      const fullPath = saveFullStory(chapters, storyInfo, tempDir)
      expect(fs.existsSync(fullPath)).toBe(true)

      const text = fs.readFileSync(fullPath, 'utf-8')
      expect(text).toContain('# My Great Adventure')
      expect(text).toContain('**Tổng số chapter:** 2')
      expect(text).toContain('## Chapter 1')
      expect(text).toContain('## Chapter 2')
    })

    it('fixes common mojibake encoding corruptions in text', () => {
      expect(fixMojibake('â€œHello Worldâ€ ')).toBe('“Hello World”')
      expect(fixMojibake('â€” dash test')).toBe('— dash test')
    })

    it('saveChapter formats image elements as ![](url) in content.md', () => {
      const chapter: ChapterContent = {
        chapter_number: 1,
        title: 'Chapter 1',
        content_elements: [
          ['image', 'https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg'],
          ['text', 'The ring arrived on a Tuesday.']
        ]
      }
      saveChapter(chapter, tempDir)
      const content = fs.readFileSync(path.join(tempDir, 'chapter_01', 'content.md'), 'utf-8')
      expect(content).toContain('![](https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg)')
      expect(content).toContain('The ring arrived on a Tuesday.')
    })

    it('saveChapter converts raw image URL in text elements to ![](url) in content.md', () => {
      const chapter: ChapterContent = {
        chapter_number: 2,
        title: 'Chapter 2',
        content_elements: [
          ['text', 'https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg'],
          ['text', 'The ring arrived on a Tuesday.']
        ]
      }
      saveChapter(chapter, tempDir)
      const content = fs.readFileSync(path.join(tempDir, 'chapter_02', 'content.md'), 'utf-8')
      expect(content).toContain('![](https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg)')
    })

    it('saveFullStory includes image elements formatted as ![](url)', () => {
      const chapters: ChapterContent[] = [
        {
          chapter_number: 1,
          title: 'Chapter 1',
          content_elements: [
            ['image', 'https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg'],
            ['text', 'The ring arrived on a Tuesday.']
          ]
        }
      ]
      const storyInfo: StoryInfo = {
        title: 'Test Story',
        slug: 'test-story',
        base_url: 'https://example.com',
        total_chapters: 1
      }
      const fullPath = saveFullStory(chapters, storyInfo, tempDir)
      const content = fs.readFileSync(fullPath, 'utf-8')
      expect(content).toContain('![](https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg)')
    })

    it('UniversalParser parses <p> tags containing raw image URLs as image elements', () => {
      const parser = new UniversalParser()
      const html = `
        <div class="entry-content">
          <p>https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg</p>
          <p>The ring arrived on a Tuesday.</p>
        </div>
      `
      const ch = parser.parseChapter(html, 1)
      expect(ch.images).toContain('https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg')
      const imgElem = ch.content_elements.find(([t]) => t === 'image')
      expect(imgElem).toBeDefined()
      expect(imgElem![1]).toBe('https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg')
    })
  })

  // ================= 2. EDGE CASES =================
  describe('Edge Cases', () => {
    it('detects single page stories when no TOC or next buttons exist', () => {
      const parser = new UniversalParser()
      const singlePageHtml = `
        <!DOCTYPE html>
        <html>
        <head><title>One Shot Story</title></head>
        <body>
          <h1>One Shot Story</h1>
          <article class="prose">
            <p>This is a complete short story that lives entirely on this single page.</p>
            <p>It does not have any next or previous chapter links whatsoever.</p>
          </article>
        </body>
        </html>
      `
      const info = parser.getStoryInfo(singlePageHtml, 'https://example.com/short-story')
      expect(info.is_single_page).toBe(true)
      expect(info.total_chapters).toBe(1)
    })

    it('sanitizes folder names with illegal characters', () => {
      expect(sanitizeFolderName('Story: The Hero / The Villain? *<Awesome>*')).toBe(
        'Story- The Hero - The Villain- --Awesome'
      )
      expect(sanitizeFolderName('')).toBe('story')
      expect(sanitizeFolderName('...---...')).toBe('story')
    })

    it('handles empty or malformed HTML safely without throwing', () => {
      const parser = new UniversalParser()
      const emptyInfo = parser.getStoryInfo('', 'https://example.com/test')
      expect(emptyInfo.title).toBeDefined()
      expect(emptyInfo.total_chapters).toBe(1)

      const emptyChapter = parser.parseChapter('', 1)
      expect(emptyChapter.chapter_number).toBe(1)
      expect(emptyChapter.title).toBe('Chapter 1')
      expect(emptyChapter.paragraphs).toEqual([])
      expect(emptyChapter.content_elements).toEqual([])
    })

    it('correctly detects 10 chapters in TreeIQ when both desktop and mobile TOC exist (prevents 21-chapter bug)', () => {
      const parser = new TreeIQParser()
      // HTML containing both desktop and mobile TOC lists, each with 10 chapters + 1 intro item
      const treeIqHtml = `
        <!DOCTYPE html>
        <html>
        <head>
          <title>A Great Sad Story | TreeIQ</title>
        </head>
        <body>
          <h1 class="v5-title">A Great Sad Story</h1>
          <span class="breadcrumb-item">Chapter 1 / 10</span>
          <!-- Desktop TOC -->
          <ol id="chapter-toc-list-desktop">
            <li><a href="/blog/sad-story/chapter-1">Chapter 1</a></li>
            <li><a href="/blog/sad-story/chapter-2">Chapter 2</a></li>
            <li><a href="/blog/sad-story/chapter-3">Chapter 3</a></li>
            <li><a href="/blog/sad-story/chapter-4">Chapter 4</a></li>
            <li><a href="/blog/sad-story/chapter-5">Chapter 5</a></li>
            <li><a href="/blog/sad-story/chapter-6">Chapter 6</a></li>
            <li><a href="/blog/sad-story/chapter-7">Chapter 7</a></li>
            <li><a href="/blog/sad-story/chapter-8">Chapter 8</a></li>
            <li><a href="/blog/sad-story/chapter-9">Chapter 9</a></li>
            <li><a href="/blog/sad-story/chapter-10">Chapter 10</a></li>
          </ol>
          <!-- Mobile TOC with extra intro item -->
          <ol id="chapter-toc-list">
            <li><a href="/blog/sad-story">Introduction</a></li>
            <li><a href="/blog/sad-story/chapter-1">Chapter 1</a></li>
            <li><a href="/blog/sad-story/chapter-2">Chapter 2</a></li>
            <li><a href="/blog/sad-story/chapter-3">Chapter 3</a></li>
            <li><a href="/blog/sad-story/chapter-4">Chapter 4</a></li>
            <li><a href="/blog/sad-story/chapter-5">Chapter 5</a></li>
            <li><a href="/blog/sad-story/chapter-6">Chapter 6</a></li>
            <li><a href="/blog/sad-story/chapter-7">Chapter 7</a></li>
            <li><a href="/blog/sad-story/chapter-8">Chapter 8</a></li>
            <li><a href="/blog/sad-story/chapter-9">Chapter 9</a></li>
            <li><a href="/blog/sad-story/chapter-10">Chapter 10</a></li>
          </ol>
        </body>
        </html>
      `
      const info = parser.getStoryInfo(treeIqHtml, 'https://sad.treeiq.biz/blog/sad-story')
      expect(info.total_chapters).toBe(10)
    })

    it('does not inflate chapter count from other stories in footer / related posts in UniversalParser', () => {
      const parser = new UniversalParser()
      const htmlWithRelated = `
        <!DOCTYPE html>
        <html>
        <head><title>My Story</title></head>
        <body>
          <h1>My Story</h1>
          <div class="chapter-list">
            <a href="/my-story/chapter-1">Chapter 1</a>
            <a href="/my-story/chapter-2">Chapter 2</a>
            <a href="/my-story/chapter-3">Chapter 3</a>
          </div>
          <!-- Related stories widget in sidebar or footer -->
          <div class="related-stories">
            <a href="/another-story/chapter-21">Another Novel Chapter 21</a>
          </div>
        </body>
        </html>
      `
      const info = parser.getStoryInfo(htmlWithRelated, 'https://example.com/my-story/chapter-1')
      expect(info.total_chapters).toBe(3)
    })
  })

  // ================= 3. ERROR HANDLING & CONTROLS =================
  describe('Error Handling & Engine Controls', () => {
    it('returns error when url is empty', async () => {
      const engine = new StoryScraperEngine()
      const res = await engine.run({ url: '' })
      expect(res.ok).toBe(false)
      expect(res.message).toContain('Chưa nhập URL')
    })

    it('aborts early when cancelled', async () => {
      let isCancelled = true
      const engine = new StoryScraperEngine({
        isCancelled: () => isCancelled
      })

      const res = await engine.run({ url: 'https://example.com/story' })
      expect(res.ok).toBe(false)
      expect(res.message).toContain('hủy')
    })
  })
})
