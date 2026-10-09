import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import { DatabaseService } from '../src/main/services/database'
import { checkVideoFilesBatch } from '../src/main/services/video-checker'
import { determineVideoStatus, STATUS_POSTED, STATUS_CONTENT_DONE, STATUS_VIDEO_READY, STATUS_FETCH_VIDEO, STATUS_FAILED } from '../src/main/services/status-engine'

describe('Full Lifecycle Workflow Integration Test', () => {
  let tempDir: string
  let testDbPath: string
  let videoDir: string
  let sampleDir: string
  let db: DatabaseService

  beforeEach(async () => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'banwin-lifecycle-'))
    testDbPath = path.join(tempDir, 'lifecycle_app.db')
    videoDir = path.join(tempDir, 'AI_VIDEO')
    sampleDir = path.join(tempDir, 'short_drama')
    fs.mkdirSync(videoDir, { recursive: true })
    fs.mkdirSync(sampleDir, { recursive: true })

    db = new DatabaseService(testDbPath)
    await db.initialize()
  })

  afterEach(() => {
    db.close()
    try {
      fs.rmSync(tempDir, { recursive: true, force: true })
    } catch {}
  })

  // 1. HAPPY PATH: Full End-to-End Progression
  describe('Happy Path: Complete Lifecycle Progression', () => {
    it('progresses correctly through FETCH VIDEO -> VIDEO READY -> CONTENT DONE -> POSTED', () => {
      // Step 1: Bulk insert Reels
      const reels = [
        'https://www.facebook.com/reel/100000001',
        'https://www.facebook.com/reel/100000002'
      ]
      const inserted = db.bulkInsertReels(reels, true)
      expect(inserted).toHaveLength(2)

      const row1 = db.getVideoByStt('1')!
      expect(row1.status).toBe(STATUS_FETCH_VIDEO)
      expect(db.getStatCounts().fetch_video).toBe(2)

      // Step 2: Video file arrives on disk in AI_VIDEO
      const videoFile = path.join(videoDir, '1.mp4')
      fs.writeFileSync(videoFile, Buffer.alloc(1024 * 1024)) // 1MB

      // Batch check detects video on disk
      const checkResult = checkVideoFilesBatch([row1], videoDir)
      expect(checkResult['1'].exists).toBe(true)

      // Status updates to VIDEO READY
      const statusAfterVideo = determineVideoStatus(row1, checkResult['1'].exists)
      expect(statusAfterVideo).toBe(STATUS_VIDEO_READY)
      db.upsertVideo({ ...row1, status: statusAfterVideo, link_video: videoFile })

      let updated = db.getVideoByStt('1')!
      expect(updated.status).toBe(STATUS_VIDEO_READY)
      expect(db.getStatCounts().video_ready).toBe(1)

      // Step 3: Content is generated and saved
      const contentText = 'Tóm tắt câu chuyện kịch tính tập 1...'
      const statusAfterContent = determineVideoStatus(
        { ...updated, content: contentText },
        true
      )
      expect(statusAfterContent).toBe(STATUS_CONTENT_DONE)
      db.upsertVideo({ ...updated, content: contentText, status: statusAfterContent })

      updated = db.getVideoByStt('1')!
      expect(updated.status).toBe(STATUS_CONTENT_DONE)
      expect(db.getStatCounts().content_done).toBe(1)

      // Step 4: Video is posted to Facebook
      const postUrl = 'https://facebook.com/permalink.php?story_fbid=555'
      const statusAfterPost = determineVideoStatus(
        { ...updated, bai_viet_da_dang: postUrl },
        true
      )
      expect(statusAfterPost).toBe(STATUS_POSTED)
      db.upsertVideo({ ...updated, bai_viet_da_dang: postUrl, status: statusAfterPost })

      updated = db.getVideoByStt('1')!
      expect(updated.status).toBe(STATUS_POSTED)
      expect(db.getStatCounts().posted).toBe(1)
    })
  })

  // 2. EDGE CASES
  describe('Edge Cases in Workflow', () => {
    it('handles duplicate Reels in bulk insert seamlessly', () => {
      const urls = [
        'https://fb.com/reel/999',
        'https://fb.com/reel/999',
        'https://fb.com/reel/888'
      ]
      const inserted = db.bulkInsertReels(urls, true)
      expect(inserted).toHaveLength(2)
      expect(db.getNextStt()).toBe(3)
    })
  })

  // 3. ERROR HANDLING & USER OVERRIDES
  describe('Error Handling & Overrides', () => {
    it('keeps FAILED status when user marks failed despite having video and content', () => {
      const row = {
        stt: '10',
        bai_goc: 'https://fb.com/reel/10',
        content: 'Nội dung test',
        status: STATUS_FAILED
      }
      db.upsertVideo(row)

      const fetched = db.getVideoByStt('10')!
      expect(fetched.status).toBe(STATUS_FAILED)

      const recomputed = determineVideoStatus(fetched, true)
      expect(recomputed).toBe(STATUS_FAILED)
    })
  })
})
