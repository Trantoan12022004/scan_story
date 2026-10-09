import axios from 'axios'

export interface ChapterContent {
  chapter_number: number
  title: string
  paragraphs: string[]
  images?: string[]
  content_elements: Array<[string, string]>
}

export function cleanTranslatedMarkdown(text: string): string {
  if (!text) return ''
  // Bold: ** text ** -> **text**
  let res = text.replace(/\*\*\s+([^*]+?)\s+\*\*/g, '**$1**')
  // Italic: * text * -> *text*
  res = res.replace(/(?<!\*)\*\s+([^*]+?)\s+\*(?!\*)/g, '*$1*')
  // Strike: ~~ text ~~ -> ~~text~~
  res = res.replace(/~~\s+(.+?)\s+~~/g, '~~$1~~')
  return res
}

export function isImageUrl(text: string): boolean {
  if (!text) return false
  const trimmed = text.trim()
  if (!/^https?:\/\//i.test(trimmed)) return false
  return /^https?:\/\/[^\s"'<>]+\.(?:jpg|jpeg|png|webp|gif|avif|svg)(?:[?#][^\s"'<>]*)?$/i.test(trimmed)
}

export function generateSlug(text: string): string {
  if (!text) return ''
  // Normalize unicode accents
  let normalized = text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[đĐ]/g, 'd')
    .toLowerCase()
    .trim()

  // Replace special characters with hyphens
  normalized = normalized.replace(/[^a-z0-9\s-]/g, '')
  normalized = normalized.replace(/[\s-]+/g, '-')
  return normalized.replace(/^-+|-+$/g, '').slice(0, 120)
}

export function splitChapterByParts(chapter: ChapterContent): ChapterContent[] {
  const elements = chapter.content_elements || []
  const partIndices: Array<[number, string]> = []

  for (let idx = 0; idx < elements.length; idx++) {
    const [elemType, elemVal] = elements[idx]
    if (
      elemType === 'heading' &&
      /^(PART|PARTE|CHAPTER|CAP[IÍ]TULO)\s*\d+/i.test(elemVal.trim())
    ) {
      partIndices.push([idx, elemVal.trim()])
    }
  }

  if (partIndices.length >= 2) {
    const subChapters: ChapterContent[] = []
    for (let i = 0; i < partIndices.length; i++) {
      const [startIdx, partTitle] = partIndices[i]
      const endIdx = i + 1 < partIndices.length ? partIndices[i + 1][0] : elements.length
      const subElements = elements.slice(startIdx + 1, endIdx)
      const subParagraphs = subElements
        .filter(([t]) => ['text', 'heading', 'quote'].includes(t))
        .map(([, v]) => v)

      subChapters.push({
        chapter_number: i + 1,
        title: partTitle,
        paragraphs: subParagraphs,
        images: chapter.images,
        content_elements: subElements
      })
    }
    return subChapters
  }

  return [chapter]
}

export class TranslatorService {
  private targetLang: string
  private maxChunkChars: number

  constructor(targetLang = 'en', maxChunkChars = 3000) {
    this.targetLang = targetLang
    this.maxChunkChars = maxChunkChars
  }

  public async translateText(text: string): Promise<string> {
    const clean = (text || '').trim()
    if (!clean) return ''

    try {
      const url = 'https://clients5.google.com/translate_a/t'
      const response = await axios.get(url, {
        params: {
          client: 'dict-chrome-ex',
          sl: 'auto',
          tl: this.targetLang,
          q: clean
        },
        timeout: 15000,
        headers: {
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
      })

      if (response.status === 200 && Array.isArray(response.data) && response.data[0]) {
        const trans = response.data[0][0]
        if (typeof trans === 'string') {
          return cleanTranslatedMarkdown(trans)
        }
      }
    } catch (err) {
      console.warn(`[TranslatorService] translateText error: ${err}`)
    }
    return text
  }

  public async translateElements(
    elements: Array<[string, string]>
  ): Promise<Array<[string, string]>> {
    if (!elements || elements.length === 0) return []

    const result: Array<[string, string]> = []
    let batchTexts: string[] = []
    let batchIndices: number[] = []
    let currentLen = 0

    for (let idx = 0; idx < elements.length; idx++) {
      const [elemType, elemVal] = elements[idx]
      if (['text', 'heading', 'quote'].includes(elemType)) {
        const trimmed = elemVal.trim()
        if (!trimmed) {
          result.push([elemType, elemVal])
          continue
        }

        if (elemType === 'text' && isImageUrl(trimmed)) {
          if (batchTexts.length > 0) {
            const translatedBatch = await this.translateBatch(batchTexts)
            for (let bIdx = 0; bIdx < batchIndices.length; bIdx++) {
              result.push([elements[batchIndices[bIdx]][0], translatedBatch[bIdx]])
            }
            batchTexts = []
            batchIndices = []
            currentLen = 0
          }
          result.push(['image', trimmed])
          continue
        }

        if (currentLen + trimmed.length > this.maxChunkChars && batchTexts.length > 0) {
          const translatedBatch = await this.translateBatch(batchTexts)
          for (let bIdx = 0; bIdx < batchIndices.length; bIdx++) {
            result.push([elements[batchIndices[bIdx]][0], translatedBatch[bIdx]])
          }
          batchTexts = []
          batchIndices = []
          currentLen = 0
        }

        batchTexts.push(trimmed)
        batchIndices.push(idx)
        currentLen += trimmed.length
      } else {
        if (batchTexts.length > 0) {
          const translatedBatch = await this.translateBatch(batchTexts)
          for (let bIdx = 0; bIdx < batchIndices.length; bIdx++) {
            result.push([elements[batchIndices[bIdx]][0], translatedBatch[bIdx]])
          }
          batchTexts = []
          batchIndices = []
          currentLen = 0
        }
        result.push([elemType, elemVal])
      }
    }

    if (batchTexts.length > 0) {
      const translatedBatch = await this.translateBatch(batchTexts)
      for (let bIdx = 0; bIdx < batchIndices.length; bIdx++) {
        result.push([elements[batchIndices[bIdx]][0], translatedBatch[bIdx]])
      }
    }

    return result
  }

  private async translateBatch(texts: string[]): Promise<string[]> {
    const delimiter = '\n====SPLIT====\n'
    const combined = texts.join(delimiter)

    try {
      const url = 'https://clients5.google.com/translate_a/t'
      const response = await axios.get(url, {
        params: {
          client: 'dict-chrome-ex',
          sl: 'auto',
          tl: this.targetLang,
          q: combined
        },
        timeout: 20000,
        headers: {
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
      })

      if (response.status === 200 && Array.isArray(response.data) && response.data[0]) {
        const translatedCombined = String(response.data[0][0])
        const parts = translatedCombined.split('====SPLIT====')
        if (parts.length === texts.length) {
          return parts.map((p) => cleanTranslatedMarkdown(p.trim()))
        }
      }
    } catch (err) {
      console.warn(`[TranslatorService] translateBatch error: ${err}`)
    }

    // Fallback: individual translation
    const fallbackResults: string[] = []
    for (const t of texts) {
      fallbackResults.push(await this.translateText(t))
    }
    return fallbackResults
  }

  public async translateChapter(chapter: ChapterContent): Promise<ChapterContent> {
    const transTitle = chapter.title ? await this.translateText(chapter.title) : chapter.title
    const transElements = await this.translateElements(chapter.content_elements)
    const transParagraphs = transElements
      .filter(([t]) => ['text', 'heading', 'quote'].includes(t))
      .map(([, v]) => v)

    return {
      chapter_number: chapter.chapter_number,
      title: transTitle,
      paragraphs: transParagraphs,
      images: chapter.images,
      content_elements: transElements
    }
  }
}
