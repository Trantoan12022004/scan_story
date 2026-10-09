import React, { useState, useEffect, useMemo, useRef } from 'react'
import {
  Search,
  Plus,
  RefreshCw,
  FolderSync,
  DownloadCloud,
  Edit2,
  Trash2,
  CheckCircle2,
  Clock,
  Check,
  AlertCircle,
  FileCheck2,
  Film,
  Sparkles,
  Copy,
  Play,
  Link2,
  Eye,
  Heart,
  MessageSquare,
  BarChart2,
  RotateCw
} from 'lucide-react'
import { VideoItem, StatCounts } from '../types'
import { getStatusStyle } from '../lib/status-styles'
import { formatStatNumber, formatStatsTime } from '../lib/format-stats'
import { BulkAddModal } from '../components/BulkAddModal'
import { EditVideoModal } from '../components/EditVideoModal'
import { VideoPreviewModal, PreviewVideoData } from '../components/VideoPreviewModal'
import { InAppBrowserModal, BrowserUrlData } from '../components/InAppBrowserModal'

export const QuanLyPage: React.FC = () => {
  const [videos, setVideos] = useState<VideoItem[]>([])
  const [stats, setStats] = useState<StatCounts>({
    total: 0,
    fetch_video: 0,
    video_ready: 0,
    content_done: 0,
    posted: 0,
    failed: 0
  })
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState<string>('ALL')
  const [isLoading, setIsLoading] = useState(false)
  const [isBatchMerging, setIsBatchMerging] = useState(false)
  const [videoFileMap, setVideoFileMap] = useState<Record<string, any>>({})
  const [sampleFileMap, setSampleFileMap] = useState<Record<string, any>>({})

  // Modals & Single-Active State (Automatically ends previous video/link)
  const [isBulkAddOpen, setIsBulkAddOpen] = useState(false)
  const [editingVideo, setEditingVideo] = useState<VideoItem | null>(null)
  const [previewVideo, setPreviewVideo] = useState<PreviewVideoData | null>(null)
  const [inAppBrowser, setInAppBrowser] = useState<BrowserUrlData | null>(null)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [nextStt, setNextStt] = useState(1)
  const [scanningStatsMap, setScanningStatsMap] = useState<Record<string, boolean>>({})
  const [isBatchScanningStats, setIsBatchScanningStats] = useState(false)
  const [batchScanProgress, setBatchScanProgress] = useState<{ current: number; total: number; stt?: string } | null>(null)
  const isExtractingBaoGocRef = useRef(false)

  // Background auto-extraction of bao_goc when bai_goc is present
  const triggerBackgroundBaoGocExtract = async (targets: VideoItem[]) => {
    if (isExtractingBaoGocRef.current || targets.length === 0) return
    isExtractingBaoGocRef.current = true
    try {
      for (const row of targets) {
        if (!row.bai_goc) continue
        try {
          const bg = await window.api.ai.extractBaoGoc(row.bai_goc)
          if (bg) {
            await window.api.db.updateSingleField(row.stt, 'bao_goc', bg)
            setVideos((prev) =>
              prev.map((item) => (item.stt === row.stt ? { ...item, bao_goc: bg } : item))
            )
          }
        } catch {
          // Continue to next item
        }
      }
    } finally {
      isExtractingBaoGocRef.current = false
    }
  }

  const loadData = async () => {
    setIsLoading(true)
    try {
      // 1. Auto-merge content for any rows with bao_moi immediately in background
      try {
        await window.api.ai.autoMergeAll()
      } catch (e) {
        console.warn('Auto-merge during loadData warning:', e)
      }

      const allVideos = await window.api.db.getVideos()

      // Calculate next STT for bulk add
      const maxStt = allVideos.reduce((max, v) => {
        const num = parseInt(v.stt, 10)
        return !isNaN(num) && num > max ? num : max
      }, 0)
      setNextStt(maxStt + 1)

      // Check file existence on disk & auto sync statuses into DB
      if (allVideos.length > 0) {
        const [vBatch, sBatch] = await Promise.all([
          window.api.video.checkBatch(allVideos, true),
          window.api.video.checkSampleBatch(allVideos)
        ])
        setVideoFileMap(vBatch)
        setSampleFileMap(sBatch)
      }

      // Re-fetch fresh videos & stats after status sync
      const [freshVideos, statCounts] = await Promise.all([
        window.api.db.getVideos(),
        window.api.db.getStatCounts()
      ])

      setVideos(freshVideos)
      setStats(statCounts)

      // 2. Auto-extract bao_goc for rows that have bai_goc but no bao_goc
      const missingBaoGoc = freshVideos.filter((v) => Boolean(v.bai_goc) && !Boolean(v.bao_goc))
      if (missingBaoGoc.length > 0) {
        setTimeout(() => triggerBackgroundBaoGocExtract(missingBaoGoc), 200)
      }
    } catch (err) {
      console.error('Failed to load videos:', err)
    } finally {
      setIsLoading(false)
    }
  }


  useEffect(() => {
    loadData()

    // Listen to background sample queue updates
    const unsub = window.api.sampleQueue.onEvent((event) => {
      if (event.type === 'completed' || event.type === 'failed') {
        loadData()
      }
    })

    // Listen to background stats batch scanning progress
    const unsubStats = window.api.stats?.onBatchProgress?.((progress) => {
      setBatchScanProgress(progress)
    })

    return () => {
      unsub()
      if (unsubStats) unsubStats()
    }
  }, [])

  const handleCopy = (text: string, key: string) => {
    if (!text) return
    navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey(null), 1800)
  }

  const handleScanFiles = async () => {
    setIsLoading(true)
    try {
      const [vBatch, sBatch] = await Promise.all([
        window.api.video.checkBatch(videos, true),
        window.api.video.checkSampleBatch(videos)
      ])
      setVideoFileMap(vBatch)
      setSampleFileMap(sBatch)

      const [freshVideos, statCounts] = await Promise.all([
        window.api.db.getVideos(),
        window.api.db.getStatCounts()
      ])
      setVideos(freshVideos)
      setStats(statCounts)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDownloadAllMissingSamples = async () => {
    const missing = videos.filter((v) => {
      const info = sampleFileMap[v.stt]
      return (!info || !info.exists) && Boolean(v.bai_goc)
    })

    if (missing.length === 0) {
      alert('Tất cả bài gốc đã có video mẫu trên ổ cứng.')
      return
    }

    const items = missing.map((v) => ({ stt: v.stt, url: v.bai_goc! }))
    await window.api.sampleQueue.enqueueBatch(items)
    alert(`Đã thêm ${items.length} video vào hàng đợi tải ngầm.`)
  }

  // Batch merge content = Reel caption + Báo mới (& extract Báo gốc)
  const handleBatchMergeContent = async () => {
    setIsBatchMerging(true)
    try {
      const res = await window.api.ai.batchMergeContent()
      alert(`🎉 Đã tự động ghép Báo mới & bóc tách Báo gốc thành công cho ${res.updatedCount} dòng!`)
      await loadData()
    } catch (err: any) {
      alert(`Lỗi ghép content hàng loạt: ${err.message}`)
    } finally {
      setIsBatchMerging(false)
    }
  }

  // Single extract bao_goc for a row
  const handleExtractBaoGocRow = async (stt: string, baiGoc: string) => {
    try {
      const bg = await window.api.ai.extractBaoGoc(baiGoc)
      if (bg) {
        await window.api.db.updateSingleField(stt, 'bao_goc', bg)
        loadData()
      } else {
        alert(`Không tìm thấy link báo gốc trong bài viết #${stt}`)
      }
    } catch (err: any) {
      alert(`Lỗi lấy báo gốc: ${err.message}`)
    }
  }

  const handleScanSingleStat = async (stt: string, url: string) => {
    if (!url || scanningStatsMap[stt]) return
    setScanningStatsMap((prev) => ({ ...prev, [stt]: true }))
    try {
      const stats = await window.api.stats.scanAndUpdate(stt, url)
      if (stats) {
        setVideos((prev) =>
          prev.map((v) =>
            v.stt === stt
              ? {
                ...v,
                views_count: stats.views,
                likes_count: stats.likes,
                comments_count: stats.comments,
                stats_updated_at: stats.scanned_at
              }
              : v
          )
        )
      }
    } catch (err: any) {
      console.error('Lỗi khi quét thống kê:', err)
      alert(`Không thể quét thống kê bài viết #${stt}: ${err?.message || 'Lỗi kết nối'}`)
    } finally {
      setScanningStatsMap((prev) => ({ ...prev, [stt]: false }))
    }
  }

  const handleBatchScanStats = async () => {
    const targets = videos.filter((v) => Boolean(v.bai_viet_da_dang))
    if (targets.length === 0) {
      alert('Chưa có bài viết nào có link "Bài đã đăng" để quét!')
      return
    }

    setIsBatchScanningStats(true)
    setBatchScanProgress({ current: 0, total: targets.length })

    try {
      const items = targets.map((v) => ({ stt: v.stt, url: v.bai_viet_da_dang! }))
      const results = await window.api.stats.scanBatch(items)
      if (results) {
        setVideos((prev) =>
          prev.map((v) => {
            const updated = results[v.stt]
            if (updated) {
              return {
                ...v,
                views_count: updated.views,
                likes_count: updated.likes,
                comments_count: updated.comments,
                stats_updated_at: updated.scanned_at
              }
            }
            return v
          })
        )
      }
    } catch (err: any) {
      console.error('Lỗi khi quét tương tác hàng loạt:', err)
      alert(`Lỗi khi quét tương tác hàng loạt: ${err?.message || 'Đã xảy ra sự cố'}`)
    } finally {
      setIsBatchScanningStats(false)
      setBatchScanProgress(null)
    }
  }

  const handleDelete = async (stt: string) => {
    if (confirm(`Bạn có chắc muốn xóa dòng STT #${stt}?`)) {
      await window.api.db.deleteVideo(stt)
      loadData()
    }
  }

  const handleStatusChange = async (stt: string, newStatus: string) => {
    await window.api.db.updateSingleField(stt, 'status', newStatus)
    loadData()
  }

  // Filtered rows
  const filteredVideos = useMemo(() => {
    return videos.filter((item) => {
      if (activeFilter !== 'ALL' && item.status !== activeFilter) {
        return false
      }
      if (search.trim()) {
        const q = search.toLowerCase()
        const matchStt = item.stt.toLowerCase().includes(q)
        const matchTitle = (item.bao_moi || '').toLowerCase().includes(q)
        const matchBaoGoc = (item.bao_goc || '').toLowerCase().includes(q)
        const matchPrompt = (item.prompt_video || '').toLowerCase().includes(q)
        const matchContent = (item.content || '').toLowerCase().includes(q)
        const matchReel = (item.bai_goc || '').toLowerCase().includes(q)
        return matchStt || matchTitle || matchBaoGoc || matchPrompt || matchContent || matchReel
      }
      return true
    })
  }, [videos, activeFilter, search])

  const statCards = [
    { id: 'ALL', label: 'Tổng số', count: stats.total, border: 'border-slate-300', text: 'text-slate-900', icon: Film, dot: 'bg-slate-700' },
    { id: 'FETCH VIDEO', label: 'Lấy video', count: stats.fetch_video, border: 'border-blue-300 hover:border-blue-400', text: 'text-blue-700', icon: Clock, dot: 'bg-blue-600' },
    { id: 'VIDEO READY', label: 'Xong video', count: stats.video_ready, border: 'border-emerald-300 hover:border-emerald-400', text: 'text-emerald-700', icon: Check, dot: 'bg-emerald-600' },
    { id: 'CONTENT DONE', label: 'Xong nội dung', count: stats.content_done, border: 'border-purple-300 hover:border-purple-400', text: 'text-purple-700', icon: FileCheck2, dot: 'bg-purple-600' },
    { id: 'POSTED', label: 'Đã đăng bài', count: stats.posted, border: 'border-amber-300 hover:border-amber-400', text: 'text-amber-800', icon: CheckCircle2, dot: 'bg-amber-600' },
    { id: 'FAILED', label: 'Không tạo được', count: stats.failed, border: 'border-rose-300 hover:border-rose-400', text: 'text-rose-700', icon: AlertCircle, dot: 'bg-rose-600' }
  ]

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden bg-slate-50 text-slate-800">
      {/* Top Stat Dashboard */}
      <div className="p-5 pb-3 border-b border-slate-200/80 bg-white shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-slate-900 flex items-center gap-2">
              Quản lý tiến độ video
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Bảng quản lý 10 cột chuẩn • Video Preview tức thì • Trình duyệt In-App không gián đoạn
            </p>
          </div>

          {/* Quick Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsBulkAddOpen(true)}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-md shadow-indigo-600/20 active:scale-95 transition"
            >
              <Plus className="w-4 h-4" />
              <span>Thêm hàng loạt bài gốc</span>
            </button>

            {/* Ghép Báo Mới Button */}
            <button
              onClick={handleBatchMergeContent}
              disabled={isBatchMerging || isLoading}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 shadow-md shadow-emerald-600/20 active:scale-95 transition"
              title="Tự động trích xuất caption Reels (bỏ link cũ) + ghép link Báo Mới và lấy Báo Gốc"
            >
              <Sparkles className={`w-4 h-4 ${isBatchMerging ? 'animate-spin' : ''}`} />
              <span>{isBatchMerging ? 'Đang ghép...' : 'Ghép Báo Mới'}</span>
            </button>

            {/* Quét Tương Tác Button */}
            <button
              onClick={handleBatchScanStats}
              disabled={isBatchScanningStats || isLoading}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-sky-600 text-white hover:bg-sky-700 shadow-md shadow-sky-600/20 active:scale-95 transition"
              title="Tự động quét số view, like, comment của tất cả bài viết đã đăng"
            >
              <BarChart2 className={`w-4 h-4 ${isBatchScanningStats ? 'animate-pulse' : ''}`} />
              <span>
                {isBatchScanningStats && batchScanProgress
                  ? `Đang quét (${batchScanProgress.current}/${batchScanProgress.total})...`
                  : 'Quét tương tác bài đăng'}
              </span>
            </button>

            <button
              onClick={handleScanFiles}
              disabled={isLoading}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200 transition"
              title="Quét lại ổ cứng để cập nhật kích thước video"
            >
              <FolderSync className="w-4 h-4 text-emerald-600" />
              <span>Quét file video</span>
            </button>

            <button
              onClick={handleDownloadAllMissingSamples}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200 transition"
              title="Tải tất cả video mẫu chưa có"
            >
              <DownloadCloud className="w-4 h-4 text-indigo-600" />
              <span>Tải mẫu hàng loạt</span>
            </button>

            <button
              onClick={loadData}
              disabled={isLoading}
              className="p-2 rounded-xl bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-200 transition"
              title="Làm mới dữ liệu"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* 6 Stat Cards */}
        <div className="grid grid-cols-6 gap-3">
          {statCards.map((sc) => {
            const Icon = sc.icon
            const isSelected = activeFilter === sc.id
            return (
              <button
                key={sc.id}
                onClick={() => setActiveFilter(sc.id)}
                className={`p-3 rounded-xl border text-left transition-all relative overflow-hidden flex items-center justify-between ${isSelected
                  ? 'ring-2 ring-indigo-500 bg-indigo-50/70 shadow-sm border-indigo-200'
                  : 'bg-white hover:bg-slate-50 shadow-sm'
                  } ${sc.border}`}
              >
                <div>
                  <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{sc.label}</p>
                  <p className={`text-xl font-bold tracking-tight mt-0.5 ${sc.text || 'text-slate-800'}`}>
                    {sc.count}
                  </p>
                </div>
                <div className={`p-2 rounded-lg bg-slate-50 border border-slate-100 ${sc.text || 'text-slate-400'}`}>
                  <Icon className="w-4 h-4" />
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="px-5 py-3 border-b border-slate-200/80 bg-slate-50 flex items-center justify-between">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm theo STT, tiêu đề, báo gốc, link, nội dung..."
            className="w-full pl-9 pr-4 py-1.5 rounded-xl bg-white border border-slate-300 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-indigo-500 transition shadow-sm"
          />
        </div>

        <div className="text-xs text-slate-500 flex items-center gap-2">
          <span>Hiển thị: <strong className="text-slate-800">{filteredVideos.length}</strong> / {videos.length} dòng</span>
          {activeFilter !== 'ALL' && (
            <button
              onClick={() => setActiveFilter('ALL')}
              className="text-indigo-600 hover:underline font-semibold text-[11px]"
            >
              (Xóa lọc)
            </button>
          )}
        </div>
      </div>

      {/* Main Table Container - 10 Cột Chuẩn */}
      <div className="flex-1 overflow-auto bg-white">
        <table className="w-full text-left border-collapse text-xs">
          <thead className="sticky top-0 z-20 bg-slate-100 text-slate-600 uppercase tracking-wider font-semibold border-b border-slate-200 text-[11px]">
            <tr>
              <th className="py-2.5 px-3 w-14 text-center">STT</th>
              <th className="py-2.5 px-3 w-36 text-center">Trạng thái</th>
              <th className="py-2.5 px-3 w-44">Bài gốc (Reels)</th>
              <th className="py-2.5 px-3 w-48">Video mẫu (AI)</th>
              <th className="py-2.5 px-3 w-44">Báo gốc</th>
              <th className="py-2.5 px-3 w-44">Tiêu đề (Báo mới)</th>
              <th className="py-2.5 px-4 min-w-[200px]">Nội dung (Content)</th>
              <th className="py-2.5 px-3 w-44">Video mới</th>
              <th className="py-2.5 px-3 w-36">Bài đã đăng</th>
              <th className="py-2.5 px-3 min-w-[170px]">Thống kê (View / Like / Cmt)</th>
              <th className="py-2.5 px-3 w-20 text-center">Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredVideos.length === 0 ? (
              <tr>
                <td colSpan={11} className="py-16 text-center text-slate-400 italic">
                  <Film className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="text-xs">Không có dữ liệu video nào phù hợp</p>
                </td>
              </tr>
            ) : (
              filteredVideos.map((row) => {
                const style = getStatusStyle(row.status)
                const vInfo = videoFileMap[row.stt] || {}
                const sInfo = sampleFileMap[row.stt] || {}

                return (
                  <tr
                    key={row.stt}
                    onDoubleClick={() => setEditingVideo(row)}
                    className={`transition-colors duration-100 ${style.rowTint}`}
                  >
                    {/* 1. STT */}
                    <td className="py-2.5 px-3 text-center font-mono font-bold text-slate-700">
                      #{row.stt}
                    </td>

                    {/* 2. Unified Status Badge with Dropdown */}
                    <td className="py-2.5 px-3 text-center">
                      <div className="inline-flex items-center gap-1.5 justify-center">
                        <span className={`w-2 h-2 rounded-full shrink-0 shadow-xs ${style.dotColor}`} />
                        <select
                          value={row.status || 'FETCH VIDEO'}
                          onChange={(e) => handleStatusChange(row.stt, e.target.value)}
                          className={`text-[11px] font-extrabold px-2.5 py-1 rounded-full border shadow-xs cursor-pointer focus:outline-none transition ${style.badgeBg} ${style.badgeText} ${style.badgeBorder}`}
                          title={style.description}
                        >
                          <option value="FETCH VIDEO" className="bg-white text-blue-900 font-bold">FETCH VIDEO</option>
                          <option value="VIDEO READY" className="bg-white text-emerald-950 font-bold">VIDEO READY</option>
                          <option value="CONTENT DONE" className="bg-white text-purple-950 font-bold">CONTENT DONE</option>
                          <option value="POSTED" className="bg-white text-amber-950 font-bold">POSTED</option>
                          <option value="FAILED" className="bg-white text-rose-950 font-bold">FAILED</option>
                        </select>
                      </div>
                    </td>

                    {/* 3. Bài gốc (Reels link) - Mở thẳng in-app & nút chép */}
                    <td className="py-2.5 px-3">
                      {row.bai_goc ? (
                        <div className="flex items-center gap-1.5 group">
                          <button
                            onClick={() => setInAppBrowser({ url: row.bai_goc!, title: `Reels #${row.stt}` })}
                            className="font-mono text-[11px] text-blue-600 hover:text-blue-800 hover:underline truncate max-w-[130px] text-left"
                            title="Bấm để mở trực tiếp trong app"
                          >
                            {row.bai_goc}
                          </button>
                          <button
                            onClick={() => handleCopy(row.bai_goc!, `bai_goc_${row.stt}`)}
                            className="text-slate-400 hover:text-slate-700 transition p-0.5"
                            title="Sao chép link Reels"
                          >
                            {copiedKey === `bai_goc_${row.stt}` ? (
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      ) : (
                        <span className="text-slate-300">-</span>
                      )}
                    </td>

                    {/* 4. Video mẫu (AI) - Click mở popup preview, có nút chép đường dẫn */}
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-1.5">
                        {sInfo.exists ? (
                          <>
                            {/* Click preview button */}
                            <button
                              onClick={() => {
                                const localP = sInfo.path || (row.video_mau && !/^https?:\/\//i.test(row.video_mau) ? row.video_mau : undefined)
                                const webU = row.video_mau && /^https?:\/\//i.test(row.video_mau) ? row.video_mau : undefined
                                setPreviewVideo({
                                  stt: row.stt,
                                  title: row.video_mau || `${row.stt}.mp4`,
                                  path: localP,
                                  url: webU,
                                  type: 'sample'
                                })
                              }}
                              className="px-2 py-0.5 rounded-md font-mono text-[10px] font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 flex items-center gap-1 transition cursor-pointer"
                              title="Bấm để xem trước video mẫu"
                            >
                              <Play className="w-2.5 h-2.5 fill-emerald-600 text-emerald-600" />
                              <span>{sInfo.size}</span>
                            </button>

                            {/* Copy path button */}
                            <button
                              onClick={() => handleCopy(sInfo.path || row.video_mau || '', `s_path_${row.stt}`)}
                              className="p-1 rounded text-slate-400 hover:text-indigo-600 hover:bg-slate-100 transition"
                              title="Sao chép đường dẫn video mẫu"
                            >
                              {copiedKey === `s_path_${row.stt}` ? (
                                <Check className="w-3.5 h-3.5 text-emerald-600" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={async () => {
                              if (row.bai_goc) {
                                await window.api.sampleQueue.enqueue({ stt: row.stt, url: row.bai_goc })
                              } else {
                                alert('Chưa có link bài gốc để tải!')
                              }
                            }}
                            className="px-2 py-0.5 rounded-md font-medium text-[10px] bg-slate-100 text-slate-600 hover:bg-indigo-600 hover:text-white border border-slate-200 transition flex items-center gap-1"
                            title="Bấm để tải video mẫu"
                          >
                            <DownloadCloud className="w-3 h-3" />
                            <span>Tải mẫu</span>
                          </button>
                        )}
                        <span
                          onClick={() => {
                            if (sInfo.exists || row.video_mau) {
                              const localP = sInfo.path || (row.video_mau && !/^https?:\/\//i.test(row.video_mau) ? row.video_mau : undefined)
                              const webU = row.video_mau && /^https?:\/\//i.test(row.video_mau) ? row.video_mau : undefined
                              setPreviewVideo({
                                stt: row.stt,
                                title: row.video_mau || `${row.stt}.mp4`,
                                path: localP,
                                url: webU,
                                type: 'sample'
                              })
                            }
                          }}
                          className={`text-[11px] font-mono truncate max-w-[90px] ${sInfo.exists ? 'text-slate-700 hover:text-indigo-600 cursor-pointer font-medium' : 'text-slate-400'
                            }`}
                          title={row.video_mau || `${row.stt}.mp4`}
                        >
                          {row.stt}.mp4
                        </span>

                      </div>
                    </td>

                    {/* 5. CỘT MỚI: Báo gốc (Link bài báo/nguồn tham khảo) */}
                    <td className="py-2.5 px-3">
                      {row.bao_goc ? (
                        <div className="flex items-center gap-1.5 group">
                          <button
                            onClick={() => setInAppBrowser({ url: row.bao_goc!, title: `Báo gốc #${row.stt}` })}
                            className="font-mono text-[11px] text-emerald-700 hover:text-emerald-900 hover:underline truncate max-w-[130px] text-left"
                            title={row.bao_goc}
                          >
                            {row.bao_goc}
                          </button>
                          <button
                            onClick={() => handleCopy(row.bao_goc!, `bao_goc_${row.stt}`)}
                            className="text-slate-400 hover:text-slate-700 transition p-0.5"
                            title="Sao chép link báo gốc"
                          >
                            {copiedKey === `bao_goc_${row.stt}` ? (
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      ) : row.bai_goc ? (
                        <button
                          onClick={() => handleExtractBaoGocRow(row.stt, row.bai_goc!)}
                          className="px-2 py-0.5 rounded text-[10px] text-slate-500 hover:text-emerald-700 hover:bg-emerald-50 border border-slate-200 transition flex items-center gap-1"
                          title="Tự động dò link báo gốc từ Reels"
                        >
                          <Link2 className="w-3 h-3" />
                          <span>Dò link</span>
                        </button>
                      ) : (
                        <span className="text-slate-300">-</span>
                      )}
                    </td>

                    {/* 6. Tiêu đề / Báo mới */}
                    <td className="py-2.5 px-3 font-semibold text-slate-800">
                      {row.bao_moi && /^https?:\/\//i.test(row.bao_moi) ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => setInAppBrowser({ url: row.bao_moi!, title: `Báo mới #${row.stt}` })}
                            className="line-clamp-1 text-left text-blue-600 hover:underline font-mono text-[11px]"
                            title={row.bao_moi}
                          >
                            {row.bao_moi}
                          </button>
                          <button
                            onClick={() => handleCopy(row.bao_moi!, `bao_moi_${row.stt}`)}
                            className="text-slate-400 hover:text-slate-700 transition p-0.5"
                            title="Sao chép link"
                          >
                            {copiedKey === `bao_moi_${row.stt}` ? (
                              <Check className="w-3 h-3 text-emerald-600" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                      ) : (
                        <span className="line-clamp-1" title={row.bao_moi || ''}>
                          {row.bao_moi || <span className="text-slate-400 italic font-normal">Chưa có tiêu đề</span>}
                        </span>
                      )}
                    </td>

                    {/* 6. Nội dung (Content) - Có nút chép toàn bộ nội dung */}
                    <td className="py-2.5 px-4 text-slate-600">
                      {row.content ? (
                        <div className="flex items-start gap-1.5 group">
                          <div className="line-clamp-2 leading-relaxed flex-1 select-text" title={row.content}>
                            {row.content}
                          </div>
                          <button
                            onClick={() => handleCopy(row.content!, `content_${row.stt}`)}
                            className="p-1 rounded text-slate-400 hover:text-indigo-600 hover:bg-slate-100 transition shrink-0 mt-0.5"
                            title="Sao chép nội dung bài viết"
                          >
                            {copiedKey === `content_${row.stt}` ? (
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Chưa có bài viết</span>
                      )}
                    </td>

                    {/* 8. Video mới (AI_VIDEO) - Bỏ nút mở folder, thay bằng nút Sao Chép đường dẫn */}
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-1.5">
                        {vInfo.exists ? (
                          <>
                            {/* Click preview button */}
                            <button
                              onClick={() => {
                                const localP = vInfo.path || (row.link_video && !/^https?:\/\//i.test(row.link_video) ? row.link_video : undefined)
                                const webU = row.link_video && /^https?:\/\//i.test(row.link_video) ? row.link_video : undefined
                                setPreviewVideo({
                                  stt: row.stt,
                                  title: row.link_video || `${row.stt}.mp4`,
                                  path: localP,
                                  url: webU,
                                  type: 'new'
                                })
                              }}
                              className="px-2 py-0.5 rounded-md font-mono text-[10px] font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 flex items-center gap-1 transition cursor-pointer"
                              title="Bấm để xem trước video mới"
                            >
                              <Play className="w-2.5 h-2.5 fill-emerald-600 text-emerald-600" />
                              <span>{vInfo.size}</span>
                            </button>


                            {/* Nút SAO CHÉP ĐƯỜNG DẪN (thay thế hoàn toàn nút mở video/thư mục) */}
                            <button
                              onClick={() => handleCopy(vInfo.path || row.link_video || '', `v_path_${row.stt}`)}
                              className="p-1 rounded text-slate-400 hover:text-indigo-600 hover:bg-slate-100 transition"
                              title="Sao chép đường dẫn video mới"
                            >
                              {copiedKey === `v_path_${row.stt}` ? (
                                <Check className="w-3.5 h-3.5 text-emerald-600" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </>
                        ) : (
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 text-slate-400 border border-slate-200">
                            Chưa có file
                          </span>
                        )}
                      </div>
                    </td>

                    {/* 9. Bài đã đăng - Mở thẳng in-app & nút chép */}
                    <td className="py-2.5 px-3">
                      {row.bai_viet_da_dang ? (
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => setInAppBrowser({ url: row.bai_viet_da_dang!, title: `Bài đã đăng #${row.stt}` })}
                            className="truncate max-w-[100px] text-amber-600 hover:text-amber-800 hover:underline font-mono text-[11px] text-left"
                            title="Bấm để xem trực tiếp trong app"
                          >
                            {row.bai_viet_da_dang}
                          </button>
                          <button
                            onClick={() => handleCopy(row.bai_viet_da_dang!, `bai_dang_${row.stt}`)}
                            className="text-slate-400 hover:text-slate-700 transition p-0.5"
                            title="Sao chép link bài đã đăng"
                          >
                            {copiedKey === `bai_dang_${row.stt}` ? (
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      ) : (
                        <span className="text-slate-300">-</span>
                      )}
                    </td>

                    {/* 10. Thống kê tương tác (View / Like / Cmt) */}
                    <td className="py-2.5 px-3">
                      {row.bai_viet_da_dang ? (
                        <div className="flex items-center gap-2">
                          <div
                            className="flex items-center gap-1.5 bg-slate-50 border border-slate-200/90 rounded-lg px-2 py-1 shadow-xs hover:border-slate-300 transition"
                            title={
                              row.stats_updated_at
                                ? `Lần quét gần nhất: ${formatStatsTime(row.stats_updated_at)}`
                                : 'Chưa quét số liệu tương tác. Bấm nút ⟳ để quét'
                            }
                          >
                            {/* View count */}
                            <span
                              className="inline-flex items-center gap-1 text-[11px] font-bold text-sky-700"
                              title={`Lượt xem: ${(row.views_count || 0).toLocaleString('vi-VN')}`}
                            >
                              <Eye className="w-3 h-3 text-sky-500 shrink-0" />
                              <span>{formatStatNumber(row.views_count)}</span>
                            </span>

                            <span className="text-slate-300">|</span>

                            {/* Like count */}
                            <span
                              className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-600"
                              title={`Lượt thích: ${(row.likes_count || 0).toLocaleString('vi-VN')}`}
                            >
                              <Heart className="w-3 h-3 text-rose-500 fill-rose-500/20 shrink-0" />
                              <span>{formatStatNumber(row.likes_count)}</span>
                            </span>

                            <span className="text-slate-300">|</span>

                            {/* Comment count */}
                            <span
                              className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700"
                              title={`Bình luận: ${(row.comments_count || 0).toLocaleString('vi-VN')}`}
                            >
                              <MessageSquare className="w-3 h-3 text-emerald-500 shrink-0" />
                              <span>{formatStatNumber(row.comments_count)}</span>
                            </span>
                          </div>

                          {/* Re-scan button */}
                          <button
                            onClick={() => handleScanSingleStat(row.stt, row.bai_viet_da_dang!)}
                            disabled={scanningStatsMap[row.stt]}
                            className="p-1 rounded-md text-slate-400 hover:text-sky-600 hover:bg-sky-50 border border-transparent hover:border-sky-200 transition"
                            title="Quét lại số view, like, cmt từ bài viết đã đăng"
                          >
                            <RotateCw
                              className={`w-3.5 h-3.5 ${scanningStatsMap[row.stt] ? 'animate-spin text-sky-600' : ''
                                }`}
                            />
                          </button>
                        </div>
                      ) : (
                        <span className="text-slate-300">-</span>
                      )}
                    </td>

                    {/* 10. Thao tác */}
                    <td className="py-2.5 px-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => setEditingVideo(row)}
                          className="p-1 rounded-lg text-slate-400 hover:text-indigo-600 hover:bg-slate-100 transition"
                          title="Chỉnh sửa chi tiết"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(row.stt)}
                          className="p-1 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-slate-100 transition"
                          title="Xóa dòng"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Bulk Add Modal */}
      <BulkAddModal
        isOpen={isBulkAddOpen}
        onClose={() => setIsBulkAddOpen(false)}
        onSuccess={() => loadData()}
        nextStt={nextStt}
      />

      {/* Edit Video Modal */}
      <EditVideoModal
        isOpen={Boolean(editingVideo)}
        onClose={() => setEditingVideo(null)}
        video={editingVideo}
        onSave={() => loadData()}
      />

      {/* Video Preview Popup (Opening another video automatically terminates the previous one) */}
      <VideoPreviewModal
        video={previewVideo}
        onClose={() => setPreviewVideo(null)}
      />

      {/* In-App Browser Modal (Opens any link directly in app; opening another link automatically ends previous link) */}
      <InAppBrowserModal
        urlItem={inAppBrowser}
        onClose={() => setInAppBrowser(null)}
      />
    </div>
  )
}
