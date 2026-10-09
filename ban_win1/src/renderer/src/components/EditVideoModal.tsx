import React, { useState, useEffect } from 'react'
import {
  X,
  Save,
  FileText,
  FolderOpen,
  Bot,
  Sparkles,
  Link2,
  Copy,
  Check,
  Globe,
  Eye,
  Heart,
  MessageSquare,
  BarChart2,
  RotateCw
} from 'lucide-react'
import { VideoItem } from '../types'
import { STATUS_STYLES } from '../lib/status-styles'
import { formatStatNumber, formatStatsTime } from '../lib/format-stats'
import { InAppBrowserModal, BrowserUrlData } from './InAppBrowserModal'

interface EditVideoModalProps {
  isOpen: boolean
  onClose: () => void
  video: VideoItem | null
  onSave: () => void
}

export const EditVideoModal: React.FC<EditVideoModalProps> = ({
  isOpen,
  onClose,
  video,
  onSave
}) => {
  if (!isOpen || !video) return null

  const [formData, setFormData] = useState<VideoItem>({ ...video })
  const [isAiLoading, setIsAiLoading] = useState(false)
  const [isCaptionLoading, setIsCaptionLoading] = useState(false)
  const [isBaoGocLoading, setIsBaoGocLoading] = useState(false)
  const [isMergeLoading, setIsMergeLoading] = useState(false)
  const [isScanningStats, setIsScanningStats] = useState(false)
  const [inAppUrl, setInAppUrl] = useState<BrowserUrlData | null>(null)
  const [copiedField, setCopiedField] = useState<string | null>(null)

  // Helper to create content: content = caption reels (bài gốc, đã loại bỏ link đính kèm) + link báo mới
  const buildReelContent = async (
    bmUrl: string,
    bgUrl?: string,
    currentContent?: string,
    forceReExtract = false
  ) => {
    const bm = (bmUrl || '').trim()
    const bg = (bgUrl || '').trim()
    const cur = (currentContent !== undefined ? currentContent : formData.content) || ''

    if (typeof (window.api?.ai as any)?.createContent === 'function') {
      const res = await (window.api.ai as any).createContent({
        baiGoc: bg,
        baoMoi: bm,
        currentContent: cur,
        forceReExtract
      })
      return res?.content || ''
    }

    // Fallback for hot-reloaded sessions:
    let baseCaption = ''
    if (!forceReExtract && cur) {
      const cleanCur = cur.replace(/https?:\/\/[^\s"'<>]+/gi, '').trim()
      if (cleanCur.length >= 25) {
        baseCaption = cleanCur
      }
    }

    if (!baseCaption && bg && window.api?.ai?.extractCaption) {
      try {
        const ext = await window.api.ai.extractCaption(bg)
        if (ext) baseCaption = ext
      } catch { }
    }

    if (!baseCaption && cur) {
      baseCaption = cur.replace(/https?:\/\/[^\s"'<>]+/gi, '').trim()
    }

    return await window.api.ai.mergeContent(baseCaption, bm)
  }

  // Auto-merge content helper: when bao_moi is present, merge immediately without waiting
  const autoMergeContent = async (bmUrl: string, currentContent?: string) => {
    const bm = (bmUrl || '').trim()
    if (!bm) return
    const content = (currentContent !== undefined ? currentContent : formData.content) || ''
    const cleanCur = content.replace(/https?:\/\/[^\s"'<>]+/gi, '').trim()
    if (content.includes(bm) && cleanCur.length >= 25) return

    setIsMergeLoading(true)
    try {
      const merged = await buildReelContent(bm, formData.bai_goc, content)
      if (merged) {
        setFormData((prev) => ({ ...prev, content: merged }))
      }
    } catch (e) {
      console.warn('Auto merge error:', e)
    } finally {
      setIsMergeLoading(false)
    }
  }

  // Auto-extract bao_goc helper: when bai_goc is present, automatically scan original article
  const autoExtractBaoGoc = async (bgUrl: string) => {
    const url = (bgUrl || '').trim()
    if (!url || formData.bao_goc) return
    setIsBaoGocLoading(true)
    try {
      const bg = await window.api.ai.extractBaoGoc(url)
      if (bg) {
        setFormData((prev) => (prev.bao_goc ? prev : { ...prev, bao_goc: bg }))
      }
    } catch (e) {
      console.warn('Auto extract bao_goc error:', e)
    } finally {
      setIsBaoGocLoading(false)
    }
  }

  // When modal opens: auto-extract bao_goc and auto-merge content if conditions met
  useEffect(() => {
    if (!isOpen || !video) return
    setFormData({ ...video })

    // 1. Auto-extract bao_goc in background if missing
    const bgUrl = (video.bai_goc || '').trim()
    const hasBaoGoc = Boolean((video.bao_goc || '').trim())
    if (bgUrl && !hasBaoGoc) {
      setIsBaoGocLoading(true)
      window.api.ai
        .extractBaoGoc(bgUrl)
        .then((bg) => {
          if (bg) {
            setFormData((prev) => (prev.bao_goc ? prev : { ...prev, bao_goc: bg }))
          }
        })
        .catch(() => { })
        .finally(() => setIsBaoGocLoading(false))
    }

    // 2. Auto-merge content if bao_moi is present
    const bmUrl = (video.bao_moi || '').trim()
    const content = (video.content || '').trim()
    const cleanCur = content.replace(/https?:\/\/[^\s"'<>]+/gi, '').trim()
    if (bmUrl && (!content.includes(bmUrl) || cleanCur.length < 25)) {
      autoMergeContent(bmUrl, content)
    }
  }, [isOpen, video?.stt])

  const handleChange = (field: keyof VideoItem, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }


  const handleCopy = (text: string, fieldName: string) => {
    if (text) {
      navigator.clipboard.writeText(text)
      setCopiedField(fieldName)
      setTimeout(() => setCopiedField(null), 2000)
    }
  }

  const handleScanStatsFromUrl = async () => {
    if (!formData.bai_viet_da_dang) {
      alert('Vui lòng nhập link bài viết đã đăng trước khi quét!')
      return
    }
    setIsScanningStats(true)
    try {
      const stats = await window.api.stats.scanPost(formData.bai_viet_da_dang)
      if (stats) {
        setFormData((prev) => ({
          ...prev,
          views_count: stats.views,
          likes_count: stats.likes,
          comments_count: stats.comments,
          stats_updated_at: stats.scanned_at
        }))
      }
    } catch (e: any) {
      console.error('Lỗi khi quét tương tác:', e)
      alert(`Lỗi quét tương tác: ${e?.message || 'Không thể lấy dữ liệu'}`)
    } finally {
      setIsScanningStats(false)
    }
  }

  const handleChooseFile = async (field: 'link_video' | 'video_mau') => {
    const chosen = await window.api.dialog.openFile([
      { name: 'Video MP4', extensions: ['mp4', 'mkv', 'avi'] }
    ])
    if (chosen) {
      handleChange(field, chosen)
    }
  }

  const handleExtractCaption = async () => {
    if (!formData.bai_goc) {
      alert('Vui lòng nhập Link bài gốc trước!')
      return
    }
    setIsCaptionLoading(true)
    try {
      const caption = await window.api.ai.extractCaption(formData.bai_goc)
      if (caption) {
        handleChange('content', caption)
      } else {
        alert('Không tìm thấy caption từ liên kết này.')
      }
    } catch (err: any) {
      alert(`Lỗi trích xuất caption: ${err.message}`)
    } finally {
      setIsCaptionLoading(false)
    }
  }

  const handleExtractBaoGoc = async () => {
    if (!formData.bai_goc) {
      alert('Vui lòng nhập Link bài gốc (Reels) trước!')
      return
    }
    setIsBaoGocLoading(true)
    try {
      const bg = await window.api.ai.extractBaoGoc(formData.bai_goc)
      if (bg) {
        handleChange('bao_goc', bg)
      } else {
        alert('Không tìm thấy link báo gốc trong bài viết hoặc comment của tác giả.')
      }
    } catch (err: any) {
      alert(`Lỗi lấy báo gốc: ${err.message}`)
    } finally {
      setIsBaoGocLoading(false)
    }
  }

  const handleMergeContent = async () => {
    if (!formData.bao_moi && !formData.bai_goc && !formData.content) {
      alert('Cần có link bài gốc (Facebook Reel) hoặc link Báo mới để ghép!')
      return
    }
    setIsMergeLoading(true)
    try {
      const merged = await buildReelContent(
        formData.bao_moi || '',
        formData.bai_goc || '',
        formData.content || '',
        true // force re-extract from reel to guarantee fresh caption
      )
      if (merged) {
        handleChange('content', merged)
      }
    } catch (err: any) {
      alert(`Lỗi ghép content: ${err.message}`)
    } finally {
      setIsMergeLoading(false)
    }
  }

  const handleGenerateAi = async () => {
    if (!formData.content) {
      alert('Cần có nội dung ban đầu (caption) để AI tạo nội dung mới!')
      return
    }
    setIsAiLoading(true)
    try {
      const defaultPrompt =
        'Dựa trên thông tin tóm tắt sau đây, hãy viết lại một bài đăng Facebook hấp dẫn, cuốn hút, có icon và hashtag liên quan:'
      const res = await window.api.ai.generateContent(defaultPrompt, formData.content)
      if (res) {
        handleChange('content', res)
      }
    } catch (err: any) {
      alert(`Lỗi AI: ${err.message}`)
    } finally {
      setIsAiLoading(false)
    }
  }

  const handleSubmit = async () => {
    try {
      let finalData = { ...formData }
      const bm = (finalData.bao_moi || '').trim()
      const content = (finalData.content || '').trim()
      const cleanCur = content.replace(/https?:\/\/[^\s"'<>]+/gi, '').trim()
      // Auto merge if bao_moi is set and content is missing bao_moi or missing reel caption
      if (bm && (!content.includes(bm) || cleanCur.length < 25)) {
        const merged = await buildReelContent(bm, finalData.bai_goc, content)
        if (merged) {
          finalData.content = merged
        }
      }
      await window.api.db.upsertVideo(finalData)
      onSave()
      onClose()
    } catch (err: any) {
      alert(`Lỗi lưu dữ liệu: ${err.message}`)
    }
  }


  const statuses = ['FETCH VIDEO', 'VIDEO READY', 'CONTENT DONE', 'POSTED', 'FAILED']

  return (
    <>
      <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
        <div className="bg-white border border-slate-200 rounded-2xl w-full max-w-3xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden animate-in fade-in zoom-in-95 duration-150">
          {/* Header */}
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-3">
              <span className="px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-600 font-mono font-bold text-sm border border-indigo-100">
                #{formData.stt}
              </span>
              <h3 className="font-bold text-base text-slate-900">Chỉnh sửa chi tiết video</h3>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Form Body */}
          <div className="p-6 overflow-y-auto space-y-4">
            {/* Row 1: Status & Tiêu đề Báo mới */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider flex items-center justify-between">
                  <span>Trạng thái thống nhất</span>
                  <span className="text-[10px] text-slate-500 font-normal lowercase">(tự động hoặc đổi thủ công)</span>
                </label>
                <div className="relative flex items-center">
                  <span
                    className={`absolute left-3 w-2.5 h-2.5 rounded-full shrink-0 shadow-xs ${STATUS_STYLES[formData.status || 'FETCH VIDEO']?.dotColor || 'bg-blue-600'
                      }`}
                  />
                  <select
                    value={formData.status || 'FETCH VIDEO'}
                    onChange={(e) => handleChange('status', e.target.value)}
                    className={`w-full pl-8 pr-3.5 py-2 text-xs font-extrabold rounded-xl border focus:outline-none focus:ring-2 focus:ring-indigo-500 transition shadow-xs ${STATUS_STYLES[formData.status || 'FETCH VIDEO']?.badgeBg || 'bg-blue-100'
                      } ${STATUS_STYLES[formData.status || 'FETCH VIDEO']?.badgeText || 'text-blue-900'
                      } ${STATUS_STYLES[formData.status || 'FETCH VIDEO']?.badgeBorder || 'border-blue-400'
                      }`}
                  >
                    {statuses.map((s) => (
                      <option key={s} value={s} className="bg-white text-slate-900 font-bold">
                        {s} — {STATUS_STYLES[s]?.labelVi || s}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">
                  Tiêu đề / Báo mới (Link báo mới)
                </label>
                <input
                  type="text"
                  value={formData.bao_moi || ''}
                  onChange={(e) => handleChange('bao_moi', e.target.value)}
                  onBlur={(e) => {
                    const bm = e.target.value.trim()
                    if (bm && !formData.content?.includes(bm)) {
                      autoMergeContent(bm)
                    }
                  }}
                  placeholder="Tiêu đề hoặc đường dẫn link báo mới..."
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2 text-xs text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500"
                />
              </div>

            </div>

            {/* Row 2: Bài gốc (Reels link) */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">
                Bài gốc (Link Facebook Reels)
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={formData.bai_goc || ''}
                  onChange={(e) => handleChange('bai_goc', e.target.value)}
                  onBlur={(e) => {
                    const bg = e.target.value.trim()
                    if (bg && !formData.bao_goc) {
                      autoExtractBaoGoc(bg)
                    }
                  }}
                  placeholder="https://www.facebook.com/reel/..."
                  className="flex-1 bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2 text-xs text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
                />

                {formData.bai_goc && (
                  <>
                    <button
                      type="button"
                      onClick={() => handleCopy(formData.bai_goc!, 'bai_goc')}
                      className="px-3 py-2 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-slate-900 transition flex items-center gap-1"
                      title="Sao chép link Reels"
                    >
                      {copiedField === 'bai_goc' ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                    </button>
                    <button
                      type="button"
                      onClick={() => setInAppUrl({ url: formData.bai_goc!, title: `Reels #${formData.stt}` })}
                      className="px-3 py-2 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-600 hover:bg-indigo-100 transition flex items-center gap-1"
                      title="Xem trực tiếp trong app"
                    >
                      <Globe className="w-4 h-4" />
                      <span className="text-[11px] font-semibold">Xem in-app</span>
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Row 3: Báo gốc (Link bài báo/nguồn gốc tham khảo) */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Báo gốc (Link nguồn / báo gốc lấy từ Reels hoặc comment tác giả)
                </label>
                <button
                  type="button"
                  disabled={isBaoGocLoading}
                  onClick={handleExtractBaoGoc}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100 transition"
                  title="Tự động tìm kiếm link bài báo gốc từ caption hoặc comment của tác giả"
                >
                  <Link2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>{isBaoGocLoading ? 'Đang dò link...' : 'Lấy tự động từ bài gốc'}</span>
                </button>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={formData.bao_goc || ''}
                  onChange={(e) => handleChange('bao_goc', e.target.value)}
                  placeholder="https://vnexpress.net/... hoặc bài báo gốc"
                  className="flex-1 bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2 text-xs text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
                />
                {formData.bao_goc && (
                  <>
                    <button
                      type="button"
                      onClick={() => handleCopy(formData.bao_goc!, 'bao_goc')}
                      className="px-3 py-2 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-slate-900 transition flex items-center gap-1"
                      title="Sao chép link báo gốc"
                    >
                      {copiedField === 'bao_goc' ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                    </button>
                    <button
                      type="button"
                      onClick={() => setInAppUrl({ url: formData.bao_goc!, title: `Báo gốc #${formData.stt}` })}
                      className="px-3 py-2 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-600 hover:bg-indigo-100 transition flex items-center gap-1"
                      title="Xem trong ứng dụng"
                    >
                      <Globe className="w-4 h-4" />
                      <span className="text-[11px] font-semibold">Xem in-app</span>
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Row 4: Video mẫu & Video mới */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">
                  Video mẫu (Phân tích AI)
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={formData.video_mau || ''}
                    onChange={(e) => handleChange('video_mau', e.target.value)}
                    placeholder="C:\Users\...\short_drama\37.mp4"
                    className="flex-1 bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-800 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => handleCopy(formData.video_mau || '', 'video_mau')}
                    className="p-2 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-slate-900 transition"
                    title="Sao chép đường dẫn"
                  >
                    {copiedField === 'video_mau' ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleChooseFile('video_mau')}
                    className="p-2 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-slate-900 transition"
                    title="Chọn file trên máy"
                  >
                    <FolderOpen className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">
                  Video mới (Đăng bài)
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={formData.link_video || ''}
                    onChange={(e) => handleChange('link_video', e.target.value)}
                    placeholder="C:\...\AI_VIDEO\37.mp4"
                    className="flex-1 bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-800 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => handleCopy(formData.link_video || '', 'link_video')}
                    className="p-2 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-slate-900 transition"
                    title="Sao chép đường dẫn"
                  >
                    {copiedField === 'link_video' ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleChooseFile('link_video')}
                    className="p-2 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-slate-900 transition"
                    title="Chọn file trên máy"
                  >
                    <FolderOpen className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Row 5: Prompt Video */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">
                Prompt Video / Ghi chú tạo video
              </label>
              <textarea
                rows={2}
                value={formData.prompt_video || ''}
                onChange={(e) => handleChange('prompt_video', e.target.value)}
                placeholder="Prompt hướng dẫn Gemini hoặc mô tả nội dung video..."
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2 text-xs text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Row 6: Content (Bài viết) with AI & Merge actions */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Nội dung bài viết (Content hoàn chỉnh)
                </label>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleCopy(formData.content || '', 'content')}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 border border-slate-200 text-slate-700 hover:bg-slate-200 transition"
                    title="Sao chép toàn bộ nội dung bài viết"
                  >
                    {copiedField === 'content' ? (
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                    <span>{copiedField === 'content' ? 'Đã chép' : 'Sao chép'}</span>
                  </button>

                  <button
                    type="button"
                    disabled={isMergeLoading}
                    onClick={handleMergeContent}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition shadow-xs"
                    title="Tự động ghép Caption Reels (bỏ link cũ) + Link Báo Mới"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                    <span>{isMergeLoading ? 'Đang ghép...' : '✨ Ghép Content (Reel + Báo mới)'}</span>
                  </button>

                  <button
                    type="button"
                    disabled={isCaptionLoading}
                    onClick={handleExtractCaption}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 border border-slate-200 text-slate-700 hover:bg-slate-200 transition"
                  >
                    <FileText className="w-3.5 h-3.5 text-blue-600" />
                    <span>{isCaptionLoading ? 'Đang lấy...' : 'Lấy caption Reel'}</span>
                  </button>

                  <button
                    type="button"
                    disabled={isAiLoading}
                    onClick={handleGenerateAi}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 transition"
                  >
                    <Bot className="w-3.5 h-3.5 text-indigo-600" />
                    <span>{isAiLoading ? 'AI đang tạo...' : 'DeepSeek'}</span>
                  </button>
                </div>
              </div>
              <textarea
                rows={5}
                value={formData.content || ''}
                onChange={(e) => handleChange('content', e.target.value)}
                placeholder="Nội dung bài viết dùng để đăng bài..."
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2 text-xs text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Row 7: Bài viết đã đăng */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">
                Bài viết đã đăng (Link bài viết hoàn thành)
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={formData.bai_viet_da_dang || ''}
                  onChange={(e) => handleChange('bai_viet_da_dang', e.target.value)}
                  placeholder="https://facebook.com/permalink.php?..."
                  className="flex-1 bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2 text-xs text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
                />
                {formData.bai_viet_da_dang && (
                  <>
                    <button
                      type="button"
                      onClick={() => handleCopy(formData.bai_viet_da_dang!, 'bai_viet_da_dang')}
                      className="px-3 py-2 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-slate-900 transition flex items-center gap-1"
                      title="Sao chép link bài đã đăng"
                    >
                      {copiedField === 'bai_viet_da_dang' ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                    </button>
                    <button
                      type="button"
                      onClick={() => setInAppUrl({ url: formData.bai_viet_da_dang!, title: `Bài đã đăng #${formData.stt}` })}
                      className="px-3 py-2 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-600 hover:bg-indigo-100 transition flex items-center gap-1"
                      title="Xem trong ứng dụng"
                    >
                      <Globe className="w-4 h-4" />
                      <span className="text-[11px] font-semibold">Xem in-app</span>
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Row 8: Thống kê tương tác (View, Like, Cmt) */}
            <div className="p-4 bg-slate-50 border border-slate-200/80 rounded-2xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <BarChart2 className="w-4 h-4 text-sky-600" />
                  <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Thống kê tương tác bài viết (Views, Likes, Comments)
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {formData.stats_updated_at && (
                    <span className="text-[11px] text-slate-400">
                      Cập nhật: {formatStatsTime(formData.stats_updated_at)}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={handleScanStatsFromUrl}
                    disabled={isScanningStats || !formData.bai_viet_da_dang}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-sky-600 text-white hover:bg-sky-700 disabled:opacity-50 transition shadow-xs cursor-pointer"
                    title="Quét lại số view, like, comment từ link bài viết"
                  >
                    <RotateCw className={`w-3.5 h-3.5 ${isScanningStats ? 'animate-spin' : ''}`} />
                    <span>{isScanningStats ? 'Đang quét...' : 'Quét từ link'}</span>
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                {/* Views */}
                <div className="bg-white border border-slate-200 rounded-xl p-2.5 shadow-2xs">
                  <div className="flex items-center gap-1.5 mb-1 text-slate-500">
                    <Eye className="w-3.5 h-3.5 text-sky-500" />
                    <span className="text-[11px] font-semibold">Lượt xem</span>
                  </div>
                  <input
                    type="number"
                    min="0"
                    value={formData.views_count ?? 0}
                    onChange={(e) => handleChange('views_count', parseInt(e.target.value, 10) || 0)}
                    className="w-full text-sm font-bold text-sky-900 bg-transparent focus:outline-none"
                  />
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                    Hiển thị: {formatStatNumber(formData.views_count)}
                  </div>
                </div>

                {/* Likes */}
                <div className="bg-white border border-slate-200 rounded-xl p-2.5 shadow-2xs">
                  <div className="flex items-center gap-1.5 mb-1 text-slate-500">
                    <Heart className="w-3.5 h-3.5 text-rose-500 fill-rose-500/20" />
                    <span className="text-[11px] font-semibold">Lượt thích</span>
                  </div>
                  <input
                    type="number"
                    min="0"
                    value={formData.likes_count ?? 0}
                    onChange={(e) => handleChange('likes_count', parseInt(e.target.value, 10) || 0)}
                    className="w-full text-sm font-bold text-rose-900 bg-transparent focus:outline-none"
                  />
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                    Hiển thị: {formatStatNumber(formData.likes_count)}
                  </div>
                </div>

                {/* Comments */}
                <div className="bg-white border border-slate-200 rounded-xl p-2.5 shadow-2xs">
                  <div className="flex items-center gap-1.5 mb-1 text-slate-500">
                    <MessageSquare className="w-3.5 h-3.5 text-emerald-500" />
                    <span className="text-[11px] font-semibold">Bình luận</span>
                  </div>
                  <input
                    type="number"
                    min="0"
                    value={formData.comments_count ?? 0}
                    onChange={(e) => handleChange('comments_count', parseInt(e.target.value, 10) || 0)}
                    className="w-full text-sm font-bold text-emerald-900 bg-transparent focus:outline-none"
                  />
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                    Hiển thị: {formatStatNumber(formData.comments_count)}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-end gap-3 bg-slate-50/50">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
            >
              Hủy bỏ
            </button>
            <button
              onClick={handleSubmit}
              className="flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 shadow-md shadow-indigo-600/20 active:scale-95 transition"
            >
              <Save className="w-4 h-4" />
              <span>Lưu thay đổi</span>
            </button>
          </div>
        </div>
      </div>

      {/* In-App Browser Modal (Opens links directly in app; opening another link automatically ends the previous one) */}
      <InAppBrowserModal urlItem={inAppUrl} onClose={() => setInAppUrl(null)} />
    </>
  )
}
