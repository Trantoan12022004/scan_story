import React, { useState, useEffect } from 'react'
import {
  Settings,
  FolderOpen,
  Save,
  Key,
  Globe,
  CheckCircle2,
  Database,
  Trash2,
  RotateCcw,
  AlertTriangle,
  HardDrive,
  RefreshCw,
  FolderSearch,
  X,
  FileText
} from 'lucide-react'

export const CaiDatPage: React.FC = () => {
  const [videoDir, setVideoDir] = useState('')
  const [sampleVideoDir, setSampleVideoDir] = useState('')
  const [deepseekKey, setDeepseekKey] = useState('')
  const [cmsUrl, setCmsUrl] = useState('')
  const [cmsUser, setCmsUser] = useState('')
  const [cmsPass, setCmsPass] = useState('')
  const [isSaved, setIsSaved] = useState(false)

  // Database stats & Reset system state
  const [dbStats, setDbStats] = useState<{
    videosCount: number
    downloadedCount: number
    storiesCount: number
    promptsCount: number
    dbPath: string
    dbSizeBytes: number
  } | null>(null)
  const [isResetting, setIsResetting] = useState(false)
  const [resetFeedback, setResetFeedback] = useState<{
    type: 'success' | 'error'
    text: string
  } | null>(null)
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean
    title: string
    description: string
    action: 'clear_videos' | 'clear_history' | 'reset_all'
  } | null>(null)
  const [keepSettingsOnReset, setKeepSettingsOnReset] = useState(true)

  const loadSettings = async () => {
    try {
      const cfg = await window.api.db.getSettings()
      setVideoDir(cfg.video_dir || 'C:\\Users\\Trant\\Videos\\Seedance\\anhtonton\\AI_VIDEO')
      setSampleVideoDir(cfg.sample_video_dir || 'C:\\Users\\Trant\\Videos\\short_drama')
      setDeepseekKey(cfg.deepseek_api_key || '')
      setCmsUrl(cfg.cms_url || 'https://vmnewstoryus.cfx.bz')
      setCmsUser(cfg.cms_user || 'admin')
      setCmsPass(cfg.cms_pass || '')
    } catch {}
  }

  const loadStats = async () => {
    try {
      if (typeof window.api?.db?.getDatabaseStats === 'function') {
        const stats = await window.api.db.getDatabaseStats()
        setDbStats(stats)
        return
      }

      // Backward-compatible fallback for hot-reloaded sessions
      const [videos, downloaded, stories, prompts] = await Promise.all([
        window.api?.db?.getVideos?.().catch(() => []) || [],
        window.api?.db?.getDownloadedVideos?.(1000).catch(() => []) || [],
        window.api?.db?.getScrapedStories?.(1000).catch(() => []) || [],
        window.api?.db?.getPrompts?.().catch(() => []) || []
      ])

      setDbStats({
        videosCount: Array.isArray(videos) ? videos.length : 0,
        downloadedCount: Array.isArray(downloaded) ? downloaded.length : 0,
        storiesCount: Array.isArray(stories) ? stories.length : 0,
        promptsCount: Array.isArray(prompts) ? prompts.length : 0,
        dbPath: 'C:\\Users\\Trant\\AppData\\Roaming\\app\\data\\app.db',
        dbSizeBytes: 0
      })
    } catch (err) {
      console.warn('Failed to load DB stats:', err)
    }
  }

  useEffect(() => {
    loadSettings()
    loadStats()
  }, [])

  const handleChooseFolder = async (setter: (p: string) => void) => {
    const dir = await window.api.dialog.openFolder()
    if (dir) {
      setter(dir)
    }
  }

  const handleSave = async () => {
    await window.api.db.setSetting('video_dir', videoDir)
    await window.api.db.setSetting('sample_video_dir', sampleVideoDir)
    await window.api.db.setSetting('deepseek_api_key', deepseekKey)
    await window.api.db.setSetting('cms_url', cmsUrl)
    await window.api.db.setSetting('cms_user', cmsUser)
    await window.api.db.setSetting('cms_pass', cmsPass)

    setIsSaved(true)
    setTimeout(() => setIsSaved(false), 2000)
  }

  const handleOpenDbFolder = async () => {
    const targetPath = dbStats?.dbPath || 'C:\\Users\\Trant\\AppData\\Roaming\\app\\data\\app.db'
    if (window.api?.shell?.openPath) {
      await window.api.shell.openPath(targetPath)
    }
  }

  const handleExecuteResetAction = async () => {
    if (!confirmModal) return
    setIsResetting(true)
    try {
      if (confirmModal.action === 'clear_videos') {
        if (typeof window.api?.db?.clearVideos === 'function') {
          const res = await window.api.db.clearVideos()
          setResetFeedback({
            type: 'success',
            text: `Đã xóa toàn bộ ${res?.count ?? 0} video trong danh sách Quản lý!`
          })
        } else {
          // Robust fallback via per-item delete API
          const videos = (await window.api?.db?.getVideos?.()) || []
          let count = 0
          for (const v of videos) {
            if (v.stt) {
              await window.api.db.deleteVideo(v.stt)
              count++
            }
          }
          setResetFeedback({
            type: 'success',
            text: `Đã xóa toàn bộ ${count} video trong danh sách Quản lý!`
          })
        }
      } else if (confirmModal.action === 'clear_history') {
        if (typeof window.api?.db?.clearDownloadedVideos === 'function') {
          await window.api.db.clearDownloadedVideos()
          if (typeof window.api?.db?.clearScrapedStories === 'function') {
            await window.api.db.clearScrapedStories()
          }
        } else {
          const downloaded = (await window.api?.db?.getDownloadedVideos?.(1000)) || []
          for (const it of downloaded) {
            if (it.id) await window.api.db.deleteDownloadedVideo(it.id)
          }
        }
        setResetFeedback({
          type: 'success',
          text: 'Đã dọn sạch lịch sử tải Reels và truyện cào!'
        })
      } else if (confirmModal.action === 'reset_all') {
        if (typeof window.api?.db?.resetDatabase === 'function') {
          await window.api.db.resetDatabase({ keepSettings: keepSettingsOnReset })
        } else {
          // Fallback via existing individual delete methods
          const [videos, downloaded, prompts] = await Promise.all([
            window.api?.db?.getVideos?.().catch(() => []) || [],
            window.api?.db?.getDownloadedVideos?.(1000).catch(() => []) || [],
            window.api?.db?.getPrompts?.().catch(() => []) || []
          ])
          for (const v of videos) {
            if (v.stt) await window.api.db.deleteVideo(v.stt)
          }
          for (const it of downloaded) {
            if (it.id) await window.api.db.deleteDownloadedVideo(it.id)
          }
          for (const p of prompts) {
            if (p.id) await window.api.db.deletePrompt(p.id)
          }

          if (!keepSettingsOnReset) {
            await window.api.db.setSetting('video_dir', 'C:\\Users\\Trant\\Videos\\Seedance\\anhtonton\\AI_VIDEO')
            await window.api.db.setSetting('sample_video_dir', 'C:\\Users\\Trant\\Videos\\short_drama')
            await window.api.db.setSetting('deepseek_api_key', '')
            await window.api.db.setSetting('cms_url', 'https://vmnewstoryus.cfx.bz')
            await window.api.db.setSetting('cms_user', 'admin')
            await window.api.db.setSetting('cms_pass', '')
            await loadSettings()
          }
        }

        setResetFeedback({
          type: 'success',
          text: keepSettingsOnReset
            ? 'Đã reset toàn bộ dữ liệu video & lịch sử (giữ lại cấu hình API & thư mục)!'
            : 'Đã khôi phục cài đặt gốc toàn diện thành công!'
        })
        if (!keepSettingsOnReset) {
          await loadSettings()
        }
      }
      await loadStats()
    } catch (err) {
      setResetFeedback({
        type: 'error',
        text: `Có lỗi xảy ra: ${String(err)}`
      })
    } finally {
      setIsResetting(false)
      setConfirmModal(null)
      setTimeout(() => setResetFeedback(null), 5000)
    }
  }

  const formatSize = (bytes?: number): string => {
    if (!bytes || bytes === 0) return '0 KB'
    const kb = (bytes / 1024).toFixed(1)
    if (bytes > 1024 * 1024) {
      return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
    }
    return `${kb} KB`
  }

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden bg-slate-50 text-slate-800 p-6 space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold tracking-tight text-slate-900 flex items-center gap-2">
          <Settings className="w-5 h-5 text-indigo-600" />
          <span>Cấu hình hệ thống & Quản lý dữ liệu</span>
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Cài đặt đường dẫn thư mục, API Keys, tài khoản CMS và công cụ xóa/reset dữ liệu cũ
        </p>
      </div>

      <div className="max-w-3xl space-y-5 overflow-y-auto pr-2 pb-12">
        {/* Section 1: Thư mục lưu trữ video */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 space-y-4 shadow-sm">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
            1. Đường dẫn thư mục Video
          </h3>

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Thư mục Video mới (AI_VIDEO - Dùng để đăng bài)
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={videoDir}
                  onChange={(e) => setVideoDir(e.target.value)}
                  className="flex-1 rounded-xl bg-slate-50 border border-slate-300 px-3.5 py-2 text-xs font-mono text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500"
                />
                <button
                  onClick={() => handleChooseFolder(setVideoDir)}
                  className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition flex items-center gap-1.5 text-xs font-semibold border border-slate-200"
                >
                  <FolderOpen className="w-4 h-4 text-indigo-600" />
                  <span>Chọn</span>
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">
                Thư mục Video mẫu (short_drama - Dùng cho Gemini AI)
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={sampleVideoDir}
                  onChange={(e) => setSampleVideoDir(e.target.value)}
                  className="flex-1 rounded-xl bg-slate-50 border border-slate-300 px-3.5 py-2 text-xs font-mono text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500"
                />
                <button
                  onClick={() => handleChooseFolder(setSampleVideoDir)}
                  className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition flex items-center gap-1.5 text-xs font-semibold border border-slate-200"
                >
                  <FolderOpen className="w-4 h-4 text-indigo-600" />
                  <span>Chọn</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: AI Credentials */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 space-y-4 shadow-sm">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
            <Key className="w-4 h-4 text-purple-600" />
            <span>2. DeepSeek AI API Key</span>
          </h3>

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">
              API Key (Dùng để sinh nội dung bài viết và prompt tự động)
            </label>
            <input
              type="password"
              value={deepseekKey}
              onChange={(e) => setDeepseekKey(e.target.value)}
              placeholder="sk-..."
              className="w-full rounded-xl bg-slate-50 border border-slate-300 px-3.5 py-2 text-xs font-mono text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        {/* Section 3: CMS BlogBio */}
        {/* Section 3: CMS Configuration (Multi-site: BlogBio & TreeIQ) */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 space-y-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
              <Globe className="w-4 h-4 text-emerald-600" />
              <span>3. Cấu hình CMS Báo (Đăng bài tự động)</span>
            </h3>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-400 font-semibold mr-1">Chọn nhanh site:</span>
              <button
                type="button"
                onClick={() => {
                  setCmsUrl('https://vmnewstoryus.cfx.bz')
                  setCmsUser('admin')
                  setCmsPass('')
                }}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition ${
                  cmsUrl.includes('cfx.bz')
                    ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                }`}
              >
                Site 1: vmnewstoryus (BlogBio)
              </button>
              <button
                type="button"
                onClick={() => {
                  setCmsUrl('https://vmstoryab.teasy.live')
                  setCmsUser('vinhmai@teasy.live')
                  setCmsPass('Vnpt@@123456')
                }}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition ${
                  cmsUrl.includes('teasy.live')
                    ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                }`}
              >
                Site 2: vmstoryab (TreeIQ)
              </button>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-semibold text-slate-600">CMS Base URL</label>
                <span className="text-[10px] font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-100">
                  {cmsUrl.includes('teasy.live') || cmsUrl.includes('treeiq')
                    ? 'TreeIQ CMS Network'
                    : 'BlogBio (Laravel API)'}
                </span>
              </div>
              <input
                type="text"
                value={cmsUrl}
                onChange={(e) => setCmsUrl(e.target.value)}
                placeholder="https://vmstoryab.teasy.live"
                className="w-full rounded-xl bg-slate-50 border border-slate-300 px-3.5 py-2 text-xs font-mono text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Email / Tài khoản</label>
                <input
                  type="text"
                  value={cmsUser}
                  onChange={(e) => setCmsUser(e.target.value)}
                  placeholder="vinhmai@teasy.live"
                  className="w-full rounded-xl bg-slate-50 border border-slate-300 px-3.5 py-2 text-xs text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Mật khẩu</label>
                <input
                  type="password"
                  value={cmsPass}
                  onChange={(e) => setCmsPass(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl bg-slate-50 border border-slate-300 px-3.5 py-2 text-xs text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>
          </div>
        </div>


        {/* Save Button */}
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 shadow-md shadow-indigo-600/20 active:scale-95 transition"
          >
            <Save className="w-4 h-4" />
            <span>{isSaved ? 'Đã lưu cấu hình!' : 'Lưu cấu hình'}</span>
          </button>
          {isSaved && (
            <span className="text-xs text-emerald-600 flex items-center gap-1 font-semibold animate-in fade-in">
              <CheckCircle2 className="w-4 h-4" />
              <span>Cài đặt đã được áp dụng thành công.</span>
            </span>
          )}
        </div>

        {/* Section 4: Quản lý dữ liệu & Khôi phục hệ thống */}
        <div className="p-5 rounded-2xl bg-white border border-rose-200/80 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-rose-800 uppercase tracking-wider flex items-center gap-2">
              <Database className="w-4 h-4 text-rose-600" />
              <span>4. Quản lý dữ liệu & Khôi phục hệ thống (Reset)</span>
            </h3>
            <button
              onClick={loadStats}
              title="Làm mới thống kê"
              className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          <p className="text-xs text-slate-600 leading-relaxed">
            Khu vực quản lý kho lưu trữ SQLite cục bộ. Bạn có thể xem vị trí file database, xóa bảng dữ liệu cụ thể hoặc reset toàn bộ hệ thống để làm việc với danh sách mới.
          </p>

          {/* Database info card */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-700 flex items-center gap-1.5">
                <HardDrive className="w-4 h-4 text-slate-500" />
                Vị trí file dữ liệu (Database):
              </span>
              <button
                onClick={handleOpenDbFolder}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1 hover:underline"
              >
                <FolderSearch className="w-3.5 h-3.5" />
                <span>Mở thư mục chứa file</span>
              </button>
            </div>
            <div className="p-2.5 bg-white border border-slate-200/90 rounded-lg font-mono text-[11px] text-slate-600 break-all select-all">
              {dbStats?.dbPath || 'Đang tải đường dẫn...'}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-xs">
              <div className="p-2.5 rounded-lg bg-white border border-slate-200 text-center">
                <span className="block text-[11px] text-slate-500">Video Quản lý</span>
                <span className="text-sm font-bold text-slate-800 font-mono">
                  {dbStats?.videosCount ?? 0}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-white border border-slate-200 text-center">
                <span className="block text-[11px] text-slate-500">Reels đã tải</span>
                <span className="text-sm font-bold text-slate-800 font-mono">
                  {dbStats?.downloadedCount ?? 0}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-white border border-slate-200 text-center">
                <span className="block text-[11px] text-slate-500">Truyện đã cào</span>
                <span className="text-sm font-bold text-slate-800 font-mono">
                  {dbStats?.storiesCount ?? 0}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-white border border-slate-200 text-center">
                <span className="block text-[11px] text-slate-500">Dung lượng DB</span>
                <span className="text-sm font-bold text-slate-800 font-mono">
                  {formatSize(dbStats?.dbSizeBytes)}
                </span>
              </div>
            </div>
          </div>

          {/* Feedback banner */}
          {resetFeedback && (
            <div
              className={`p-3 rounded-xl text-xs font-semibold flex items-center gap-2 animate-in fade-in ${
                resetFeedback.type === 'success'
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-rose-50 text-rose-700 border border-rose-200'
              }`}
            >
              {resetFeedback.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              )}
              <span>{resetFeedback.text}</span>
            </div>
          )}

          {/* Reset actions */}
          <div className="pt-2 grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Action 1: Xóa video */}
            <button
              onClick={() =>
                setConfirmModal({
                  isOpen: true,
                  title: 'Xóa toàn bộ danh sách Video?',
                  description: `Thao tác này sẽ xóa sạch ${
                    dbStats?.videosCount ?? 0
                  } video trong trang Quản Lý. Các file video vật lý trên ổ cứng sẽ KHÔNG bị xóa.`,
                  action: 'clear_videos'
                })
              }
              className="p-3 rounded-xl border border-amber-200 bg-amber-50 hover:bg-amber-100/80 text-amber-900 transition text-left flex flex-col justify-between space-y-1.5 group"
            >
              <div className="flex items-center gap-1.5 font-bold text-xs text-amber-800">
                <Trash2 className="w-3.5 h-3.5 text-amber-600 group-hover:scale-110 transition-transform" />
                <span>Xóa trắng bảng Video</span>
              </div>
              <p className="text-[11px] text-amber-700/90 leading-tight">
                Xóa tất cả hàng video để nhập danh sách mới từ đầu.
              </p>
            </button>

            {/* Action 2: Xóa lịch sử reels & truyện */}
            <button
              onClick={() =>
                setConfirmModal({
                  isOpen: true,
                  title: 'Xóa lịch sử Tải Reels & Cào Truyện?',
                  description: `Thao tác này sẽ dọn sạch ${
                    dbStats?.downloadedCount ?? 0
                  } bản ghi tải Reels và ${
                    dbStats?.storiesCount ?? 0
                  } bản ghi truyện đã cào khỏi database.`,
                  action: 'clear_history'
                })
              }
              className="p-3 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-800 transition text-left flex flex-col justify-between space-y-1.5 group"
            >
              <div className="flex items-center gap-1.5 font-bold text-xs text-slate-700">
                <FileText className="w-3.5 h-3.5 text-slate-500 group-hover:scale-110 transition-transform" />
                <span>Xóa lịch sử Tải / Cào</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-tight">
                Xóa nhật ký tải video reels và lịch sử truyện đã cào.
              </p>
            </button>

            {/* Action 3: Reset toàn bộ */}
            <button
              onClick={() =>
                setConfirmModal({
                  isOpen: true,
                  title: 'Khôi phục cài đặt gốc (Reset toàn bộ)?',
                  description:
                    'Thao tác này sẽ dọn sạch toàn bộ database. Bạn có thể chọn giữ lại cấu hình API Keys và thư mục bên dưới.',
                  action: 'reset_all'
                })
              }
              className="p-3 rounded-xl border border-rose-300 bg-rose-50 hover:bg-rose-100 text-rose-900 transition text-left flex flex-col justify-between space-y-1.5 group"
            >
              <div className="flex items-center gap-1.5 font-bold text-xs text-rose-700">
                <RotateCcw className="w-3.5 h-3.5 text-rose-600 group-hover:-rotate-90 transition-transform" />
                <span>Reset toàn bộ hệ thống</span>
              </div>
              <p className="text-[11px] text-rose-700/90 leading-tight">
                Khôi phục database về trạng thái xuất xưởng sạch sẽ.
              </p>
            </button>
          </div>
        </div>
      </div>

      {/* Confirmation Modal */}
      {confirmModal?.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-md w-full shadow-2xl border border-slate-200 overflow-hidden">
            <div className="p-5 space-y-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-rose-100 text-rose-600">
                    <AlertTriangle className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900">{confirmModal.title}</h4>
                    <span className="text-[11px] text-slate-500">Xác nhận thao tác dữ liệu</span>
                  </div>
                </div>
                <button
                  onClick={() => setConfirmModal(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100">
                {confirmModal.description}
              </p>

              {confirmModal.action === 'reset_all' && (
                <label className="flex items-center gap-2 p-2.5 bg-indigo-50/70 border border-indigo-100 rounded-xl cursor-pointer">
                  <input
                    type="checkbox"
                    checked={keepSettingsOnReset}
                    onChange={(e) => setKeepSettingsOnReset(e.target.checked)}
                    className="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4"
                  />
                  <span className="text-xs font-semibold text-indigo-950 select-none">
                    Giữ lại cấu hình API Keys và Thư mục video (Khuyên dùng)
                  </span>
                </label>
              )}

              <div className="flex items-center justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setConfirmModal(null)}
                  disabled={isResetting}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 transition"
                >
                  Hủy bỏ
                </button>
                <button
                  type="button"
                  onClick={handleExecuteResetAction}
                  disabled={isResetting}
                  className="px-5 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 shadow-md shadow-rose-600/20 active:scale-95 transition flex items-center gap-1.5 disabled:opacity-50"
                >
                  {isResetting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>{isResetting ? 'Đang thực hiện...' : 'Xác nhận thực hiện'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
