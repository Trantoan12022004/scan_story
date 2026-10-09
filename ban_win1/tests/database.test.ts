import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import { DatabaseService } from '../src/main/services/database'

describe('Database Service - SQLite Engine & Data Access', () => {
  let tempDir: string
  let testDbPath: string
  let dbService: DatabaseService

  beforeEach(async () => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'banwin-test-db-'))
    testDbPath = path.join(tempDir, 'test_app.db')
    dbService = new DatabaseService(testDbPath)
    await dbService.initialize()
  })

  afterEach(() => {
    dbService.close()
    try {
      fs.rmSync(tempDir, { recursive: true, force: true })
    } catch { }
  })

  // 1. HAPPY PATHS
  describe('Happy Paths', () => {
    it('initializes all 5 core tables and default settings', () => {
      const settings = dbService.getAllSettings()
      expect(settings.video_dir).toBeDefined()
      expect(settings.sample_video_dir).toBeDefined()
      expect(settings.theme).toBeDefined()
    })

    it('can upsert, retrieve, and delete a video', () => {
      const ok = dbService.upsertVideo({
        stt: '1',
        bai_goc: 'https://facebook.com/reel/100',
        content: 'Nội dung test',
        link_video: 'C:\\Videos\\1.mp4'
      })
      expect(ok).toBe(true)

      const video = dbService.getVideoByStt('1')
      expect(video).toBeDefined()
      expect(video?.stt).toBe('1')
      expect(video?.status).toBe('CONTENT DONE')
      expect(video?.bai_goc).toBe('https://facebook.com/reel/100')

      const deleted = dbService.deleteVideo('1')
      expect(deleted).toBe(true)
      expect(dbService.getVideoByStt('1')).toBeNull()
    })

    it('bulk inserts Reels URLs with consecutive STT and deduplication', () => {
      const urls = [
        'https://facebook.com/reel/1',
        'https://facebook.com/reel/2',
        'https://facebook.com/reel/1' // duplicate
      ]
      const inserted = dbService.bulkInsertReels(urls, true)
      expect(inserted).toHaveLength(2)
      expect(inserted[0].stt).toBe('1')
      expect(inserted[1].stt).toBe('2')
      expect(inserted[0].status).toBe('FETCH VIDEO')
      expect(inserted[0].video_mau).toContain('1.mp4')

      const all = dbService.getAllVideos()
      expect(all).toHaveLength(2)
    })

    it('calculates correct statistical counts across all statuses', () => {
      dbService.upsertVideo({ stt: '1', bai_goc: 'https://fb.com/reel/1' }) // FETCH VIDEO
      dbService.upsertVideo({ stt: '2', link_video: 'C:\\2.mp4' }) // VIDEO READY
      dbService.upsertVideo({ stt: '3', link_video: 'C:\\3.mp4', content: 'abc' }) // CONTENT DONE
      dbService.upsertVideo({ stt: '4', bai_viet_da_dang: 'https://facebook.com/post/4' }) // POSTED
      dbService.upsertVideo({ stt: '5', status: 'FAILED' }) // FAILED

      const stats = dbService.getStatCounts()
      expect(stats.total).toBe(5)
      expect(stats.fetch_video).toBe(1)
      expect(stats.video_ready).toBe(1)
      expect(stats.content_done).toBe(1)
      expect(stats.posted).toBe(1)
      expect(stats.failed).toBe(1)
    })

    it('manages settings with get, set, and caching', () => {
      dbService.setSetting('custom_key', 'hello_world')
      expect(dbService.getSetting('custom_key')).toBe('hello_world')
      expect(dbService.getSetting('unknown_key', 'fallback')).toBe('fallback')
    })

    it('manages prompts (create, update, delete)', () => {
      const id = dbService.savePrompt('Tóm tắt nhanh', 'Prompt template body...')
      expect(id).toBeGreaterThan(0)

      let list = dbService.getAllPrompts()
      expect(list.some(p => p.name === 'Tóm tắt nhanh')).toBe(true)

      dbService.savePrompt('Tóm tắt nâng cao', 'Prompt body updated', id)
      list = dbService.getAllPrompts()
      const updated = list.find(p => p.id === id)
      expect(updated?.name).toBe('Tóm tắt nâng cao')

      dbService.deletePrompt(id)
      expect(dbService.getAllPrompts().find(p => p.id === id)).toBeUndefined()
    })

    it('manages downloaded_videos and scraped_stories', () => {
      const dlId = dbService.addDownloadedVideo({
        url: 'https://fb.com/video/99',
        title: 'Video Drama 99',
        duration: '01:30'
      })
      expect(dlId).toBeGreaterThan(0)
      expect(dbService.getDownloadedVideos()).toHaveLength(1)
      dbService.deleteDownloadedVideo(dlId)
      expect(dbService.getDownloadedVideos()).toHaveLength(0)

      const storyId = dbService.addScrapedStory({
        url: 'https://truyen.com/truyen-1',
        title: 'Truyện Hay 1',
        chapters_count: 50
      })
      expect(storyId).toBeGreaterThan(0)
      expect(dbService.getScrapedStories()).toHaveLength(1)
    })
  })

  // 2. EDGE CASES
  describe('Edge Cases', () => {
    it('calculates next STT correctly with gaps and text STTs', () => {
      dbService.upsertVideo({ stt: '5' })
      dbService.upsertVideo({ stt: '12' })
      dbService.upsertVideo({ stt: 'special-item' })
      expect(dbService.getNextStt()).toBe(13)
    })

    it('sorts naturally by STT (1, 2, 10, not 1, 10, 2)', () => {
      dbService.upsertVideo({ stt: '10' })
      dbService.upsertVideo({ stt: '2' })
      dbService.upsertVideo({ stt: '1' })

      const sorted = dbService.getAllVideos()
      expect(sorted.map(v => v.stt)).toEqual(['1', '2', '10'])
    })

    it('filters videos by search keyword and status', () => {
      dbService.upsertVideo({ stt: '1', prompt_video: 'Kiếm hiệp kỳ tình' })
      dbService.upsertVideo({ stt: '2', prompt_video: 'Hiện đại tổng tài' })

      const results = dbService.getAllVideos({ search: 'tổng tài' })
      expect(results).toHaveLength(1)
      expect(results[0].stt).toBe('2')
    })
  })

  // 3. ERROR HANDLING
  describe('Error Handling', () => {
    it('returns false when upserting video with empty STT', () => {
      expect(dbService.upsertVideo({ stt: '' })).toBe(false)
      expect(dbService.upsertVideo({ stt: '   ' })).toBe(false)
    })

    it('returns false when updating a non-allowed field', () => {
      expect(dbService.updateSingleField('1', 'dangerous_sql_injection_col', 'val')).toBe(false)
    })

    it('returns false when deleting a non-existent STT', () => {
      expect(dbService.deleteVideo('non_existent_999')).toBe(false)
    })

    it('syncStatusesWithCheck automatically updates statuses and respects manual FAILED', () => {
      dbService.upsertVideo({ stt: '1', bai_goc: 'https://fb.com/reel/1', status: 'FETCH VIDEO' })
      dbService.upsertVideo({ stt: '2', bai_goc: 'https://fb.com/reel/2', status: 'FETCH VIDEO' })
      dbService.upsertVideo({ stt: '3', bai_goc: 'https://fb.com/reel/3', content: 'Kịch bản hay', status: 'FETCH VIDEO' })
      dbService.upsertVideo({ stt: '4', bai_viet_da_dang: 'https://fb.com/post/4', status: 'FETCH VIDEO' })
      dbService.upsertVideo({ stt: '5', bai_goc: 'https://fb.com/reel/5', status: 'FAILED' })

      const items = dbService.getAllVideos()
      const checkMap: Record<string, any> = {
        '1': { exists: false, size: '', path: '' },
        '2': { exists: true, size: '2 MB', path: 'C:\\2.mp4' },
        '3': { exists: true, size: '3 MB', path: 'C:\\3.mp4' },
        '4': { exists: true, size: '4 MB', path: 'C:\\4.mp4' },
        '5': { exists: true, size: '5 MB', path: 'C:\\5.mp4' } // video exists but status is FAILED
      }

      const changed = dbService.syncStatusesWithCheck(items, checkMap)
      expect(changed).toBe(3) // items 2, 3, 4 should change

      expect(dbService.getVideoByStt('1')?.status).toBe('FETCH VIDEO')
      expect(dbService.getVideoByStt('2')?.status).toBe('VIDEO READY')
      expect(dbService.getVideoByStt('3')?.status).toBe('CONTENT DONE')
      expect(dbService.getVideoByStt('4')?.status).toBe('POSTED')
      expect(dbService.getVideoByStt('5')?.status).toBe('FAILED') // user FAILED preserved!
    })

    it('automatically transitions status when updating bai_viet_da_dang or content', () => {
      dbService.upsertVideo({ stt: '10', bai_goc: 'https://fb.com/reel/10', status: 'FETCH VIDEO' })
      expect(dbService.getVideoByStt('10')?.status).toBe('FETCH VIDEO')

      // Updating post link automatically promotes to POSTED
      dbService.updateSingleField('10', 'bai_viet_da_dang', 'https://facebook.com/posts/101010')
      expect(dbService.getVideoByStt('10')?.status).toBe('POSTED')

      // User manual FAILED is not overwritten
      dbService.updateSingleField('10', 'status', 'FAILED')
      expect(dbService.getVideoByStt('10')?.status).toBe('FAILED')
      dbService.updateSingleField('10', 'content', 'New content added')
      expect(dbService.getVideoByStt('10')?.status).toBe('FAILED')
    })
  })

  // 4. RESET & CLEAR CAPABILITIES (TDD)
  describe('Reset & Clear Capabilities', () => {
    it('clears all videos and returns exact deleted count', () => {
      dbService.upsertVideo({ stt: '1', bai_goc: 'https://fb.com/reel/1' })
      dbService.upsertVideo({ stt: '2', bai_goc: 'https://fb.com/reel/2' })
      dbService.upsertVideo({ stt: '3', bai_goc: 'https://fb.com/reel/3' })

      const res = dbService.clearAllVideos()
      expect(res.success).toBe(true)
      expect(res.count).toBe(3)
      expect(dbService.getAllVideos()).toHaveLength(0)

      // Edge case: clearing empty table returns count 0
      const res2 = dbService.clearAllVideos()
      expect(res2.success).toBe(true)
      expect(res2.count).toBe(0)
    })

    it('clears downloaded videos, scraped stories, and prompts individually', () => {
      dbService.addDownloadedVideo({ url: 'https://video1.mp4' })
      dbService.addScrapedStory({ url: 'https://truyen.com/1', title: 'Truyện 1' })
      dbService.savePrompt('Prompt 1', 'Content 1')

      expect(dbService.clearDownloadedVideos()).toEqual({ success: true, count: 1 })
      expect(dbService.clearScrapedStories()).toEqual({ success: true, count: 1 })
      expect(dbService.clearPrompts()).toEqual({ success: true, count: 1 })

      const stats = dbService.getDatabaseStats()
      expect(stats.downloadedCount).toBe(0)
      expect(stats.storiesCount).toBe(0)
      expect(stats.promptsCount).toBe(0)
    })

    it('resets entire database keeping custom settings when keepSettings is true', () => {
      dbService.setSetting('custom_key', 'custom_value')
      dbService.upsertVideo({ stt: '1', bai_goc: 'https://fb.com/reel/1' })
      dbService.addDownloadedVideo({ url: 'https://video1.mp4' })
      dbService.savePrompt('Prompt 1', 'Nội dung')

      const resetRes = dbService.resetDatabase({ keepSettings: true })
      expect(resetRes.success).toBe(true)

      const stats = dbService.getDatabaseStats()
      expect(stats.videosCount).toBe(0)
      expect(stats.downloadedCount).toBe(0)
      expect(stats.promptsCount).toBe(0)
      expect(dbService.getSetting('custom_key')).toBe('custom_value')
    })

    it('resets entire database including settings when keepSettings is false', () => {
      dbService.setSetting('custom_key', 'custom_value')
      dbService.upsertVideo({ stt: '1', bai_goc: 'https://fb.com/reel/1' })

      const resetRes = dbService.resetDatabase({ keepSettings: false })
      expect(resetRes.success).toBe(true)

      expect(dbService.getSetting('custom_key')).toBe('')
      // Default settings should still be populated
      expect(dbService.getSetting('theme')).toBe('dark')
      expect(dbService.getSetting('video_dir')).toBeDefined()
    })

    it('provides accurate database statistics and handles closed DB safely', () => {
      dbService.upsertVideo({ stt: '1' })
      const stats = dbService.getDatabaseStats()
      expect(stats.videosCount).toBe(1)
      expect(stats.dbPath).toBe(testDbPath)

      // Test closed DB error handling
      dbService.close()
      expect(dbService.clearAllVideos()).toEqual({ success: false, count: 0 })
      expect(dbService.resetDatabase()).toEqual({ success: false, message: 'Database not initialized' })
      expect(dbService.getDatabaseStats().videosCount).toBe(0)
    })

    it('persists and updates post statistics (views, likes, comments) for posted articles', () => {
      dbService.upsertVideo({
        stt: '10',
        bai_goc: 'https://fb.com/reel/10',
        bai_viet_da_dang: 'https://facebook.com/reel/123456789'
      })

      const updateRes = dbService.updatePostStats('10', {
        views: 12500,
        likes: 1200,
        comments: 88,
        scanned_at: '2026-10-07T12:00:00Z'
      })
      expect(updateRes).toBe(true)

      const video = dbService.getVideoByStt('10')
      expect(video).toBeDefined()
      expect(video?.views_count).toBe(12500)
      expect(video?.likes_count).toBe(1200)
      expect(video?.comments_count).toBe(88)
      expect(video?.stats_updated_at).toBe('2026-10-07T12:00:00Z')

      // Non-existent STT returns false
      expect(dbService.updatePostStats('999', { views: 1, likes: 1, comments: 1 })).toBe(false)
    })
  })
})

