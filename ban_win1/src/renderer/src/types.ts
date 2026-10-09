export interface VideoItem {
  id?: number
  stt: string
  status?: string
  trang_thai_video?: string
  bai_goc?: string
  video_mau?: string
  prompt_video?: string
  frame_dau_tien?: string
  bao_goc?: string
  bao_moi?: string
  trang_thai_dang_bai?: string
  content?: string
  link_video?: string
  bai_viet_da_dang?: string
  views_count?: number
  likes_count?: number
  comments_count?: number
  stats_updated_at?: string
  created_at?: string
  updated_at?: string
}

export interface PostStats {
  views: number
  likes: number
  comments: number
  scanned_at?: string
}

export interface StatCounts {
  total: number
  fetch_video: number
  video_ready: number
  content_done: number
  posted: number
  failed: number
}

export interface PromptItem {
  id: number
  name: string
  content: string
}

export interface DownloadedItem {
  id: number
  url: string
  title?: string
  duration?: string
  file_path?: string
  file_size?: string
  thumbnail_url?: string
  downloaded_at?: string
}

export interface AppSettings {
  video_dir: string
  sample_video_dir: string
  theme: string
  cms_url: string
  cms_user: string
  cms_pass: string
  deepseek_api_key?: string
}

export interface LicenseStatus {
  valid: boolean
  message: string
  user?: string
  expires?: string
  days_left?: number
  hwid: string
  source?: 'online' | 'cache'
  code?: string
}


export interface PublishingProgress {
  current: number
  total: number
  stt: string
  status: 'starting' | 'uploading' | 'captioning' | 'publishing' | 'waiting_delay' | 'success' | 'failed'
  message?: string
  postUrl?: string
  delayRemaining?: number
}

