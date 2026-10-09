/**
 * Bộ xử lý logic trạng thái video thống nhất (Unified Status Engine) cho ban_win1.
 * Cung cấp 5 trạng thái chuẩn tiếng Anh, bảng màu Badge tương phản cao và màu nền nhạt (row tint).
 * 
 * Quy tắc tự động cập nhật:
 * - Mặc định: FETCH VIDEO
 * - Có video MP4: VIDEO READY
 * - Có video + có bài viết content: CONTENT DONE
 * - Có link bài đăng: POSTED
 * - FAILED: Người dùng tự cập nhật, hệ thống tự động không ghi đè FAILED.
 */

export const STATUS_FETCH_VIDEO = 'FETCH VIDEO'
export const STATUS_VIDEO_READY = 'VIDEO READY'
export const STATUS_CONTENT_DONE = 'CONTENT DONE'
export const STATUS_POSTED = 'POSTED'
export const STATUS_FAILED = 'FAILED'

export const VALID_STATUSES = [
  STATUS_FETCH_VIDEO,
  STATUS_VIDEO_READY,
  STATUS_CONTENT_DONE,
  STATUS_POSTED,
  STATUS_FAILED
] as const

export type VideoStatus = (typeof VALID_STATUSES)[number]

export interface StatusColor {
  bg: string
  text: string
  border: string
}

// Bảng màu tương phản cao (High Contrast Palette)
export const STATUS_COLORS: Record<string, StatusColor> = {
  [STATUS_FETCH_VIDEO]: {
    bg: '#dbeafe', // Blue-100 đậm nét
    text: '#1e40af', // Blue-800
    border: '#3b82f6' // Blue-500
  },
  [STATUS_VIDEO_READY]: {
    bg: '#d1fae5', // Emerald-100
    text: '#065f46', // Emerald-800
    border: '#10b981' // Emerald-500
  },
  [STATUS_CONTENT_DONE]: {
    bg: '#ede9fe', // Purple-100
    text: '#5b21b6', // Purple-800
    border: '#8b5cf6' // Purple-500
  },
  [STATUS_POSTED]: {
    bg: '#fef3c7', // Amber-100
    text: '#92400e', // Amber-800
    border: '#f59e0b' // Amber-500
  },
  [STATUS_FAILED]: {
    bg: '#fee2e2', // Rose-100
    text: '#991b1b', // Rose-800
    border: '#ef4444' // Rose-500
  }
}

export const STATUS_ROW_TINTS: Record<string, string> = {
  [STATUS_FETCH_VIDEO]: '#eff6ff',
  [STATUS_VIDEO_READY]: '#ecfdf5',
  [STATUS_CONTENT_DONE]: '#faf5ff',
  [STATUS_POSTED]: '#fffbeb',
  [STATUS_FAILED]: '#fff1f2'
}

export const STATUS_TOOLTIPS: Record<string, string> = {
  [STATUS_FETCH_VIDEO]: 'Lấy video (mặc định khi có link Reels ở bài gốc)',
  [STATUS_VIDEO_READY]: 'Xong video (file video MP4 đã có sẵn trên máy)',
  [STATUS_CONTENT_DONE]: 'Hoàn thành nội dung (đã có video và bài viết content)',
  [STATUS_POSTED]: 'Đã đăng bài (đã có link bài viết hoàn chỉnh)',
  [STATUS_FAILED]: 'Không tạo được (người dùng tự cập nhật khi video lỗi hoặc từ chối)'
}

export function isPostUrl(val: any): boolean {
  if (!val) return false
  const s = String(val).trim().toLowerCase()
  if (!s || s === '-' || s.includes('chưa có') || s.includes('chua co') || s === 'none') {
    return false
  }
  return (
    s.startsWith('http://') ||
    s.startsWith('https://') ||
    s.includes('facebook.com') ||
    s.includes('fb.watch') ||
    s.includes('fb.com')
  )
}

export function hasContentText(val: any): boolean {
  if (!val) return false
  const s = String(val).trim().toLowerCase()
  if (!s || s === '-' || s.startsWith('chưa có') || s.startsWith('chua co')) {
    return false
  }
  return s.length > 0
}

export function determineVideoStatus(
  row: Record<string, any> | null | undefined,
  videoExists?: boolean
): string {
  if (!row) {
    return STATUS_FETCH_VIDEO
  }

  // 1. "faile người dùng tự update" -> Nếu đang ở FAILED thì giữ nguyên FAILED
  const currentStatus = String(row.status || row.trang_thai_video || '').trim()
  const statusLower = currentStatus.toLowerCase()

  if (
    statusLower === STATUS_FAILED.toLowerCase() ||
    statusLower.includes('failed') ||
    statusLower.includes('không tạo') ||
    statusLower.includes('khong tao') ||
    statusLower.includes('từ chối') ||
    statusLower.includes('tu choi')
  ) {
    return STATUS_FAILED
  }

  // 2. "có link bài đăng chuyển sang posted"
  if (isPostUrl(row.bai_viet_da_dang)) {
    return STATUS_POSTED
  }

  // Xác định video có tồn tại trên máy hay không
  let hasVideo = false
  if (videoExists !== undefined) {
    hasVideo = Boolean(videoExists)
  } else {
    const linkV = String(row.link_video || '').trim()
    hasVideo = Boolean(
      linkV &&
      linkV.toLowerCase() !== 'chưa có file' &&
      linkV !== '-' &&
      !linkV.toLowerCase().includes('chưa có')
    )
  }

  const hasContent = hasContentText(row.content)

  // 3. "có content, video chuyển sang content done"
  if (hasVideo && hasContent) {
    return STATUS_CONTENT_DONE
  }

  // 4. "có video thì chuyển sang video ready"
  if (hasVideo) {
    return STATUS_VIDEO_READY
  }

  // 5. "mặc định để fetch video"
  return STATUS_FETCH_VIDEO
}
