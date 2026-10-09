import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  parseStatNumber,
  formatStatNumber,
  parseMetricsFromText,
  extractStatsFromHtml,
  PostStatsScanner
} from '../src/main/services/post-stats-scanner'
import axios from 'axios'

vi.mock('axios')

describe('PostStatsScanner Service - Social & Web Post Statistics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ==========================================
  // 1. HAPPY PATHS
  // ==========================================
  describe('Happy Paths', () => {
    it('parses various integer and decimal formatted strings with K, M, B multipliers including Vietnamese decimal commas', () => {
      expect(parseStatNumber('500')).toBe(500)
      expect(parseStatNumber('1,250')).toBe(1250)
      expect(parseStatNumber('15.000')).toBe(15000)
      expect(parseStatNumber('1.5K')).toBe(1500)
      expect(parseStatNumber('4,4K')).toBe(4400) // Vietnamese decimal comma!
      expect(parseStatNumber('45k')).toBe(45000)
      expect(parseStatNumber('2.4M')).toBe(2400000)
      expect(parseStatNumber('1,2M')).toBe(1200000)
      expect(parseStatNumber('10M')).toBe(10000000)
      expect(parseStatNumber('1.2B')).toBe(1200000000)
      expect(parseStatNumber(345)).toBe(345)
    })

    it('formats numbers into concise human-readable badges (K, M)', () => {
      expect(formatStatNumber(0)).toBe('0')
      expect(formatStatNumber(450)).toBe('450')
      expect(formatStatNumber(1000)).toBe('1K')
      expect(formatStatNumber(1500)).toBe('1.5K')
      expect(formatStatNumber(25400)).toBe('25.4K')
      expect(formatStatNumber(100000)).toBe('100K')
      expect(formatStatNumber(1200000)).toBe('1.2M')
      expect(formatStatNumber(5000000)).toBe('5M')
    })

    it('parses metrics from Facebook Reel/post title strings (English & Vietnamese)', () => {
      // English Facebook format
      const t1 = parseMetricsFromText('4.4K views · 53 reactions | “NO! Please… don’t!” Maria’s scream...')
      expect(t1.views).toBe(4400)
      expect(t1.likes).toBe(53)
      expect(t1.comments).toBe(0)

      // Vietnamese Facebook format with decimal comma and HTML entities
      const t2 = parseMetricsFromText('4,4K l&#x1b0;&#x1ee3;t xem &#xb7; 53 c&#x1ea3;m x&#xfa;c | Tiêu đề câu chuyện')
      expect(t2.views).toBe(4400)
      expect(t2.likes).toBe(53)
      expect(t2.comments).toBe(0)

      // Reactions only
      const t3 = parseMetricsFromText('12 reactions | Part 1 **THE CRUELEST WOUNDS...')
      expect(t3.views).toBe(0)
      expect(t3.likes).toBe(12)
      expect(t3.comments).toBe(0)

      // Complete view, reaction, and comment metrics
      const t4 = parseMetricsFromText('10K views · 1.2K reactions · 350 comments | Story title')
      expect(t4.views).toBe(10000)
      expect(t4.likes).toBe(1200)
      expect(t4.comments).toBe(350)

      // Vietnamese comments and dot separator
      const t5 = parseMetricsFromText('15.000 lượt xem · 850 lượt thích · 42 bình luận | Video hot')
      expect(t5.views).toBe(15000)
      expect(t5.likes).toBe(850)
      expect(t5.comments).toBe(42)
    })

    it('extracts metrics from Twitter / OpenGraph meta tags in HTML', () => {
      const html = `
        <!DOCTYPE html>
        <html>
        <head>
          <meta name="twitter:title" content="5.2K views · 79 reactions | Story by the window" />
          <meta property="og:description" content="120 comments shared on this story" />
        </head>
        </html>
      `
      const stats = extractStatsFromHtml(html)
      expect(stats.views).toBe(5200)
      expect(stats.likes).toBe(79)
      expect(stats.comments).toBe(120)
    })

    it('extracts metrics from Schema.org JSON-LD interactionStatistic', () => {
      const html = `
        <!DOCTYPE html>
        <html>
        <head>
          <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": "Story Clip",
            "interactionStatistic": [
              {
                "@type": "InteractionCounter",
                "interactionType": { "@type": "WatchAction" },
                "userInteractionCount": 85400
              },
              {
                "@type": "InteractionCounter",
                "interactionType": { "@type": "LikeAction" },
                "userInteractionCount": 3200
              },
              {
                "@type": "InteractionCounter",
                "interactionType": { "@type": "CommentAction" },
                "userInteractionCount": 412
              }
            ]
          }
          </script>
        </head>
        <body></body>
        </html>
      `
      const stats = extractStatsFromHtml(html)
      expect(stats.views).toBe(85400)
      expect(stats.likes).toBe(3200)
      expect(stats.comments).toBe(412)
    })

    it('extracts metrics from Facebook Relay / GraphQL embedded JSON cache', () => {
      const html = `
        <html>
        <head>
          <script type="application/json" data-sjs>
          {
            "require": [
              ["RelayPrefetchedStreamCache", "next", [], [{
                "data": {
                  "node": {
                    "reaction_count": { "count": 1420 },
                    "comment_count": { "total_count": 98 },
                    "video_view_count": 35600
                  }
                }
              }]]
            ]
          }
          </script>
        </head>
        </html>
      `
      const stats = extractStatsFromHtml(html)
      expect(stats.views).toBe(35600)
      expect(stats.likes).toBe(1420)
      expect(stats.comments).toBe(98)
    })

    it('extracts metrics from Vietnamese text patterns in HTML', () => {
      const html = `
        <div class="reel-info">
          <span class="views">12.5K lượt xem</span>
          <span class="likes">1.8K lượt thích</span>
          <span class="comments">235 bình luận</span>
        </div>
      `
      const stats = extractStatsFromHtml(html)
      expect(stats.views).toBe(12500)
      expect(stats.likes).toBe(1800)
      expect(stats.comments).toBe(235)
    })

    it('extracts metrics from English metadata patterns in HTML', () => {
      const html = `
        <meta name="description" content="Watch this video with 50K views, 2.5K likes, and 120 comments on our page" />
      `
      const stats = extractStatsFromHtml(html)
      expect(stats.views).toBe(50000)
      expect(stats.likes).toBe(2500)
      expect(stats.comments).toBe(120)
    })

    it('successfully scans a URL via HTTP fallback when ytdlp is unavailable or mocked', async () => {
      const mockHtml = `
        <html>
        <head>
          <meta name="twitter:title" content="150K views · 4.2K reactions | Hot Viral Story" />
        </head>
        <body>
          <span>89 comments</span>
        </body>
        </html>
      `
      vi.mocked(axios.get).mockResolvedValueOnce({
        status: 200,
        data: mockHtml
      } as any)

      const result = await PostStatsScanner.scanPostStats('https://example.com/posts/story-1')
      expect(result.views).toBe(150000)
      expect(result.likes).toBe(4200)
      expect(result.comments).toBe(89)
      expect(result.scanned_at).toBeDefined()
    })
  })

  // ==========================================
  // 2. EDGE CASES
  // ==========================================
  describe('Edge Cases', () => {
    it('handles empty, null, or undefined URLs gracefully', async () => {
      const r1 = await PostStatsScanner.scanPostStats('')
      expect(r1).toEqual({ views: 0, likes: 0, comments: 0, scanned_at: expect.any(String) })

      const r2 = await PostStatsScanner.scanPostStats('   ')
      expect(r2).toEqual({ views: 0, likes: 0, comments: 0, scanned_at: expect.any(String) })
    })

    it('handles HTML without any statistical numbers or matching patterns', () => {
      const emptyHtml = `<html><body><p>Chỉ có bài viết thông thường không có thống kê</p></body></html>`
      const stats = extractStatsFromHtml(emptyHtml)
      expect(stats.views).toBe(0)
      expect(stats.likes).toBe(0)
      expect(stats.comments).toBe(0)
    })

    it('handles story text containing the words "like" or "view" after the separator without false positive metrics', () => {
      const storyTitle = 'Story Part 1 | She said she likes apples and enjoyed the mountain view from her window.'
      const metrics = parseMetricsFromText(storyTitle)
      expect(metrics.views).toBe(0)
      expect(metrics.likes).toBe(0)
      expect(metrics.comments).toBe(0)
    })

    it('parses dirty, spaced, or lowercase strings without crash', () => {
      expect(parseStatNumber('')).toBe(0)
      expect(parseStatNumber('abc')).toBe(0)
      expect(parseStatNumber('  12.3 k  ')).toBe(12300)
      expect(parseStatNumber('0')).toBe(0)
      expect(parseStatNumber('0 likes')).toBe(0)
    })

    it('handles partial metrics where only likes or comments are present', () => {
      const partialHtml = `<div><span>350 lượt thích</span></div>`
      const stats = extractStatsFromHtml(partialHtml)
      expect(stats.views).toBe(0)
      expect(stats.likes).toBe(350)
      expect(stats.comments).toBe(0)
    })
  })

  // ==========================================
  // 3. ERROR HANDLING
  // ==========================================
  describe('Error Handling', () => {
    it('handles axios network error / timeout without throwing exception', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network connection timed out'))

      const result = await PostStatsScanner.scanPostStats('https://facebook.com/reel/failed-network')
      expect(result.views).toBe(0)
      expect(result.likes).toBe(0)
      expect(result.comments).toBe(0)
      expect(result.scanned_at).toBeDefined()
    })

    it('does not throw when HTML contains invalid JSON in ld+json script tags', () => {
      const malformedHtml = `
        <script type="application/ld+json">
          { unquoted_key: invalid value, broken
        </script>
        <div>500 lượt xem</div>
      `
      const stats = extractStatsFromHtml(malformedHtml)
      expect(stats.views).toBe(500)
    })

    it('handles non-string axios response data gracefully', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({
        status: 200,
        data: { error: 'Not html' }
      } as any)

      const result = await PostStatsScanner.scanPostStats('https://example.com/api/post')
      expect(result.views).toBe(0)
      expect(result.likes).toBe(0)
      expect(result.comments).toBe(0)
    })
  })
})
