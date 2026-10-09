import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import {
  normalizeStt,
  buildDefaultVideoLink,
  buildDefaultSampleVideoPath,
  checkVideoFile,
  checkVideoFilesBatch,
  checkSampleVideoFile,
  checkSampleVideosBatch
} from '../src/main/services/video-checker'

describe('Video Checker Service', () => {
  let tempDir: string

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'banwin-test-video-'))
  })

  afterEach(() => {
    try {
      fs.rmSync(tempDir, { recursive: true, force: true })
    } catch {}
  })

  // 1. HAPPY PATHS
  describe('Happy Paths', () => {
    it('normalizes various STT formats correctly', () => {
      expect(normalizeStt('37')).toBe('37')
      expect(normalizeStt('37.0')).toBe('37')
      expect(normalizeStt(42)).toBe('42')
      expect(normalizeStt(' 99 ')).toBe('99')
    })

    it('builds default video link and sample video path', () => {
      const vidLink = buildDefaultVideoLink('37', tempDir)
      expect(vidLink).toBe(path.join(tempDir, '37.mp4'))

      const sampleLink = buildDefaultSampleVideoPath('37', tempDir)
      expect(sampleLink).toBe(path.join(tempDir, '37.mp4'))
    })

    it('detects existing video file and formats its size correctly', () => {
      const testFile = path.join(tempDir, '1.mp4')
      // Create a 1.5MB dummy file
      const buf = Buffer.alloc(1.5 * 1024 * 1024)
      fs.writeFileSync(testFile, buf)

      const result = checkVideoFile(testFile, '1', tempDir)
      expect(result.exists).toBe(true)
      expect(result.bytes).toBe(buf.length)
      expect(result.size).toBe('1.5 MB')
      expect(result.path).toBe(testFile)
    })

    it('batch checks multiple video files efficiently in one scan', () => {
      const file1 = path.join(tempDir, '10.mp4')
      const file2 = path.join(tempDir, '20.mp4')
      fs.writeFileSync(file1, Buffer.alloc(500 * 1024)) // 500 KB
      fs.writeFileSync(file2, Buffer.alloc(2 * 1024 * 1024)) // 2 MB

      const items = [
        { stt: '10' },
        { stt: '20' },
        { stt: '30' } // does not exist
      ]

      const batchResults = checkVideoFilesBatch(items, tempDir)
      expect(batchResults['10'].exists).toBe(true)
      expect(batchResults['10'].size).toBe('500 KB')
      expect(batchResults['20'].exists).toBe(true)
      expect(batchResults['20'].size).toBe('2.0 MB')
      expect(batchResults['30'].exists).toBe(false)
    })

    it('batch checks sample videos in short drama directory', () => {
      const sampleFile = path.join(tempDir, '55.mp4')
      fs.writeFileSync(sampleFile, Buffer.alloc(1024 * 1024))

      const items = [{ stt: '55', video_mau: sampleFile }, { stt: '56' }]
      const sampleResults = checkSampleVideosBatch(items, tempDir)

      expect(sampleResults['55'].exists).toBe(true)
      expect(sampleResults['56'].exists).toBe(false)
    })
  })

  // 2. EDGE CASES
  describe('Edge Cases', () => {
    it('handles empty or null STT gracefully', () => {
      expect(normalizeStt(null)).toBe('')
      expect(normalizeStt(undefined)).toBe('')
      expect(normalizeStt('')).toBe('')
      expect(buildDefaultVideoLink('')).toBe('')
    })

    it('handles empty item list for batch checking without errors', () => {
      const results = checkVideoFilesBatch([], tempDir)
      expect(results).toEqual({})
    })

    it('handles uppercase file extensions and case insensitivity', () => {
      const upperFile = path.join(tempDir, '77.MP4')
      fs.writeFileSync(upperFile, Buffer.alloc(100))

      const items = [{ stt: '77' }]
      const results = checkVideoFilesBatch(items, tempDir)
      expect(results['77'].exists).toBe(true)
    })
  })

  // 3. ERROR HANDLING
  describe('Error Handling', () => {
    it('handles non-existent base directory safely without crashing', () => {
      const nonExistentDir = path.join(tempDir, 'non_existent_folder_abc_123')
      const result = checkVideoFile('', '1', nonExistentDir)
      expect(result.exists).toBe(false)

      const batch = checkVideoFilesBatch([{ stt: '1' }], nonExistentDir)
      expect(batch['1'].exists).toBe(false)
    })
  })
})
