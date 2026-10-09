import { describe, it, expect } from 'vitest'
import {
  cleanTranslatedMarkdown,
  generateSlug,
  splitChapterByParts,
  isImageUrl,
  TranslatorService,
  ChapterContent
} from '../src/main/services/translator'

describe('Translator & Story Helpers', () => {
  // 1. HAPPY PATHS
  describe('Happy Paths', () => {
    it('isImageUrl correctly validates image extensions and protocols', () => {
      expect(isImageUrl('https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg')).toBe(true)
      expect(isImageUrl('https://images.example.com/banner.png')).toBe(true)
      expect(isImageUrl('https://example.com/not-image')).toBe(false)
    })

    it('translateElements keeps image elements intact and converts image URLs in text to image elements', async () => {
      const translator = new TranslatorService('en')
      const elements: Array<[string, string]> = [
        ['image', 'https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg'],
        ['text', 'https://cdn.treeiq.biz/site_101/2026/10/another-img.png']
      ]
      const res = await translator.translateElements(elements)
      expect(res[0]).toEqual(['image', 'https://cdn.treeiq.biz/site_101/2026/10/5a-bdcb6c0b-17dd-4524-ad70-b28612b26731.jpg'])
      expect(res[1]).toEqual(['image', 'https://cdn.treeiq.biz/site_101/2026/10/another-img.png'])
    })

    it('cleans spaced markdown correctly', () => {
      expect(cleanTranslatedMarkdown('** Bold text **')).toBe('**Bold text**')
      expect(cleanTranslatedMarkdown('* Italic text *')).toBe('*Italic text*')
      expect(cleanTranslatedMarkdown('~~ Strike text ~~')).toBe('~~Strike text~~')
    })

    it('generates clean SEO slugs from Vietnamese and English titles', () => {
      expect(generateSlug('Chương 1: Khởi Đầu Mới')).toBe('chuong-1-khoi-dau-moi')
      expect(generateSlug('Story: The Dragon & The Phoenix (Part 1)')).toBe('story-the-dragon-the-phoenix-part-1')
      expect(generateSlug('Special @#$% Characters!')).toBe('special-characters')
    })

    it('splits chapters containing multiple PART headings', () => {
      const chapter: ChapterContent = {
        chapter_number: 1,
        title: 'Full Episode',
        paragraphs: ['Intro', 'Body 1', 'Body 2'],
        content_elements: [
          ['heading', 'PART 1: The Beginning'],
          ['text', 'Once upon a time...'],
          ['heading', 'PART 2: The Journey'],
          ['text', 'They traveled far...']
        ]
      }

      const parts = splitChapterByParts(chapter)
      expect(parts).toHaveLength(2)
      expect(parts[0].title).toBe('PART 1: The Beginning')
      expect(parts[0].paragraphs).toEqual(['Once upon a time...'])
      expect(parts[1].title).toBe('PART 2: The Journey')
      expect(parts[1].paragraphs).toEqual(['They traveled far...'])
    })
  })

  // 2. EDGE CASES
  describe('Edge Cases', () => {
    it('handles empty or null text for markdown cleaner and slug generator', () => {
      expect(cleanTranslatedMarkdown('')).toBe('')
      expect(cleanTranslatedMarkdown(null as any)).toBe('')
      expect(generateSlug('')).toBe('')
      expect(generateSlug(null as any)).toBe('')
    })

    it('leaves chapters with single heading or no parts intact', () => {
      const chapter: ChapterContent = {
        chapter_number: 1,
        title: 'Standard Chapter',
        paragraphs: ['Only one story content'],
        content_elements: [
          ['heading', 'Introduction'],
          ['text', 'Only one story content']
        ]
      }
      const parts = splitChapterByParts(chapter)
      expect(parts).toHaveLength(1)
      expect(parts[0].title).toBe('Standard Chapter')
    })
  })
})
