import { describe, it, expect } from 'vitest'
import {
  STATUS_FETCH_VIDEO,
  STATUS_VIDEO_READY,
  STATUS_CONTENT_DONE,
  STATUS_POSTED,
  STATUS_FAILED,
  STATUS_COLORS,
  STATUS_ROW_TINTS,
  STATUS_TOOLTIPS,
  VALID_STATUSES,
  determineVideoStatus
} from '../src/main/services/status-engine'

describe('Status Engine - Core Logic & Unified Statuses', () => {
  // 1. HAPPY PATHS
  describe('Happy Paths', () => {
    it('determines FETCH VIDEO when only bai_goc is present', () => {
      const row = { stt: '1', bai_goc: 'https://www.facebook.com/reel/123456789' }
      expect(determineVideoStatus(row)).toBe(STATUS_FETCH_VIDEO)
    })

    it('determines VIDEO READY when video exists but no content', () => {
      const row = {
        stt: '2',
        bai_goc: 'https://www.facebook.com/reel/123',
        link_video: 'C:\\Videos\\2.mp4',
        content: ''
      }
      expect(determineVideoStatus(row, true)).toBe(STATUS_VIDEO_READY)
    })

    it('determines CONTENT DONE when video exists and content has text', () => {
      const row = {
        stt: '3',
        bai_goc: 'https://www.facebook.com/reel/123',
        link_video: 'C:\\Videos\\3.mp4',
        content: 'Đây là bài viết tóm tắt nội dung hấp dẫn.'
      }
      expect(determineVideoStatus(row, true)).toBe(STATUS_CONTENT_DONE)
    })

    it('determines POSTED when bai_viet_da_dang has a valid link', () => {
      const row = {
        stt: '4',
        bai_goc: 'https://www.facebook.com/reel/123',
        link_video: 'C:\\Videos\\4.mp4',
        content: 'Nội dung',
        bai_viet_da_dang: 'https://facebook.com/permalink.php?story_fbid=999'
      }
      expect(determineVideoStatus(row, true)).toBe(STATUS_POSTED)
    })

    it('provides all 5 valid statuses with colors, row tints, and tooltips', () => {
      expect(VALID_STATUSES).toHaveLength(5)
      for (const status of VALID_STATUSES) {
        expect(STATUS_COLORS[status]).toBeDefined()
        expect(STATUS_COLORS[status].bg).toMatch(/^#[0-9a-f]{6}$/i)
        expect(STATUS_COLORS[status].text).toMatch(/^#[0-9a-f]{6}$/i)
        expect(STATUS_COLORS[status].border).toMatch(/^#[0-9a-f]{6}$/i)
        expect(STATUS_ROW_TINTS[status]).toMatch(/^#[0-9a-f]{6}$/i)
        expect(STATUS_TOOLTIPS[status]).toBeDefined()
        expect(STATUS_TOOLTIPS[status].length).toBeGreaterThan(0)
      }
    })
  })

  // 2. EDGE CASES
  describe('Edge Cases', () => {
    it('handles empty row, null, or undefined gracefully', () => {
      expect(determineVideoStatus({} as any)).toBe(STATUS_FETCH_VIDEO)
      expect(determineVideoStatus(null as any)).toBe(STATUS_FETCH_VIDEO)
      expect(determineVideoStatus(undefined as any)).toBe(STATUS_FETCH_VIDEO)
    })

    it('ignores whitespace-only values in content and links', () => {
      const row = {
        stt: '5',
        bai_goc: '   ',
        link_video: '   ',
        content: '   \n  \t ',
        bai_viet_da_dang: '   '
      }
      expect(determineVideoStatus(row)).toBe(STATUS_FETCH_VIDEO)
    })

    it('ignores placeholder text for video link like "chưa có file" or "-"', () => {
      const row1 = { stt: '6', link_video: 'chưa có file', content: 'test content' }
      expect(determineVideoStatus(row1)).toBe(STATUS_FETCH_VIDEO)

      const row2 = { stt: '7', link_video: '-', content: 'test content' }
      expect(determineVideoStatus(row2)).toBe(STATUS_FETCH_VIDEO)

      const row3 = { stt: '8', link_video: 'Chưa có file MP4', content: 'test' }
      expect(determineVideoStatus(row3)).toBe(STATUS_FETCH_VIDEO)
    })

    it('detects facebook.com URL even without http protocol', () => {
      const row = {
        stt: '9',
        bai_viet_da_dang: 'facebook.com/group/permalink/123456789'
      }
      expect(determineVideoStatus(row)).toBe(STATUS_POSTED)
    })
  })

  // 3. ERROR HANDLING & USER OVERRIDES
  describe('Error Handling & User Overrides', () => {
    it('preserves FAILED status when user marks failed or "không tạo được"', () => {
      const row1 = {
        stt: '10',
        status: 'FAILED',
        link_video: 'C:\\Videos\\10.mp4',
        content: 'Some text',
        bai_viet_da_dang: 'https://fb.com/123'
      }
      expect(determineVideoStatus(row1, true)).toBe(STATUS_FAILED)

      const row2 = {
        stt: '11',
        trang_thai_video: 'không tạo được',
        bai_viet_da_dang: 'https://fb.com/123'
      }
      expect(determineVideoStatus(row2)).toBe(STATUS_FAILED)

      const row3 = {
        stt: '12',
        status: 'từ chối',
        link_video: 'C:\\12.mp4'
      }
      expect(determineVideoStatus(row3, true)).toBe(STATUS_FAILED)
    })
  })
})
