import React, { useState, useEffect, useRef } from 'react'
import {
  BookOpen,
  Play,
  Square,
  RefreshCw,
  FolderOpen,
  ExternalLink,
  Copy,
  Trash2,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Info,
  Terminal,
  Settings2,
  Eye,
  EyeOff,
  Link,
  ClipboardPaste,
  X,
  FileText
} from 'lucide-react'

import { InAppBrowserModal, BrowserUrlData } from '../components/InAppBrowserModal'

interface ToastState {
  id: number
  type: 'success' | 'warning' | 'error' | 'info'
  title: string
  message: string
}

export const CaoTruyenPage: React.FC = () => {
  // Inputs & Scraper options
  const [url, setUrl] = useState('')
  const [parser, setParser] = useState('universal')
  const [downloadImages, setDownloadImages] = useState(true)
  const [translateEn, setTranslateEn] = useState(true)
  const [publishCms, setPublishCms] = useState(true)
  const [startCh, setStartCh] = useState(1)
  const [endCh, setEndCh] = useState(0)
  const [delay, setDelay] = useState(1.0)

  // CMS Config state
  const [cmsUrl, setCmsUrl] = useState('https://vmnewstoryus.cfx.bz')
  const [cmsUser, setCmsUser] = useState('admin')
  const [cmsPass, setCmsPass] = useState('')
  const [showCmsPass, setShowCmsPass] = useState(false)
  const [isTestingCms, setIsTestingCms] = useState(false)

  // Runtime & Execution state
  const [isScraping, setIsScraping] = useState(false)
  const [progressPct, setProgressPct] = useState(0)
  const [progressStatus, setProgressStatus] = useState('')
  const [logs, setLogs] = useState<string[]>([])
  const [autoScroll, setAutoScroll] = useState(true)
  const logContainerRef = useRef<HTMLDivElement>(null)

  // History state
  const [historyItems, setHistoryItems] = useState<any[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)

  // Toast feedback state
  const [toasts, setToasts] = useState<ToastState[]>([])

  const addToast = (type: 'success' | 'warning' | 'error' | 'info', title: string, message: string) => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { id, type, title, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4000)
  }

  // Load Settings & History on mount
  useEffect(() => {
    const init = async () => {
      try {
        const settings = await window.api.db.getSettings()
        if (settings) {
          if (settings.cms_url) setCmsUrl(settings.cms_url)
          if (settings.cms_user) setCmsUser(settings.cms_user)
          if (settings.cms_pass) setCmsPass(settings.cms_pass)
        }
      } catch {}
      loadHistory()
    }
    init()
  }, [])

  // Listen to realtime logs & progress from Electron IPC
  useEffect(() => {
    const unsubLog = window.api.story.onLog((msg) => {
      setLogs((prev) => [...prev, msg])
    })

    const unsubProgress = window.api.story.onProgress((data) => {
      setProgressPct(Math.min(100, Math.max(0, Math.round(data.percent))))
      setProgressStatus(data.status || '')
    })

    return () => {
      unsubLog()
      unsubProgress()
    }
  }, [])

  // Auto scroll logs
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const loadHistory = async () => {
    setIsLoadingHistory(true)
    try {
      const items = await window.api.db.getScrapedStories(100)
      setHistoryItems(items || [])
    } catch (err: any) {
      console.warn('Load scraped history error:', err)
    } finally {
      setIsLoadingHistory(false)
    }
  }

  const handlePasteUrl = async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (text) {
        setUrl(text.trim())
        addToast('info', 'Đã dán', 'Đã dán liên kết từ clipboard.')
      }
    } catch {
      addToast('warning', 'Không thể dán', 'Vui lòng nhấn Ctrl+V vào ô URL.')
    }
  }

  const handleTestCms = async () => {
    if (!cmsUrl.trim() || !cmsUser.trim()) {
      addToast('warning', 'Chưa điền đủ thông tin', 'Vui lòng nhập CMS Base URL và tài khoản CMS.')
      return
    }

    setIsTestingCms(true)
    try {
      const res = await window.api.story.testCms(cmsUrl.trim(), cmsUser.trim(), cmsPass.trim())
      if (res.ok) {
        addToast('success', 'Kết nối thành công', 'Đăng nhập CMS BlogBio hoàn tất!')
      } else {
        addToast('error', 'Kết nối thất bại', res.error || 'Vui lòng kiểm tra lại URL, tài khoản hoặc mật khẩu CMS.')
      }
    } catch (err: any) {
      addToast('error', 'Lỗi kiểm tra', err.message || 'Không thể kết nối CMS.')
    } finally {
      setIsTestingCms(false)
    }
  }

  const handleSaveCmsConfig = async () => {
    try {
      await window.api.db.setSetting('cms_url', cmsUrl.trim())
      await window.api.db.setSetting('cms_user', cmsUser.trim())
      await window.api.db.setSetting('cms_pass', cmsPass.trim())
      addToast('success', 'Đã lưu', 'Đã cập nhật cấu hình CMS BlogBio.')
    } catch (err: any) {
      addToast('error', 'Lỗi lưu', err.message || 'Không thể lưu cấu hình CMS.')
    }
  }

  const handleStartScraping = async () => {
    const cleanUrl = url.trim()
    if (!cleanUrl) {
      addToast('warning', 'Chưa nhập link', 'Vui lòng nhập đường link truyện cần cào.')
      return
    }

    setIsScraping(true)
    setProgressPct(5)
    setProgressStatus('Đang khởi động tiến trình cào truyện...')
    setLogs([`[${new Date().toLocaleTimeString()}] Bắt đầu tác vụ cào truyện: ${cleanUrl}`])

    try {
      const options = {
        url: cleanUrl,
        downloadImages,
        translateEn,
        publishCms,
        cmsUrl: cmsUrl.trim(),
        cmsUser: cmsUser.trim(),
        cmsPass: cmsPass.trim(),
        startCh: Math.max(1, startCh),
        endCh: endCh > 0 ? endCh : 0,
        delay: Math.max(0.1, delay)
      }

      const res = await window.api.story.startScrape(options)

      if (res && res.ok) {
        addToast('success', 'Hoàn tất cào truyện!', `Đã cào thành công ${res.chapters_scraped || 0} chapter.`)
        loadHistory()
      } else {
        addToast('error', 'Lỗi cào truyện', res?.message || 'Có lỗi xảy ra trong quá trình cào.')
      }
    } catch (err: any) {
      addToast('error', 'Lỗi hệ thống', err.message || 'Tiến trình bị gián đoạn.')
    } finally {
      setIsScraping(false)
    }
  }

  const handleCancelScraping = async () => {
    try {
      await window.api.story.cancelScrape()
      setLogs((prev) => [...prev, '[!] Đang gửi lệnh dừng khẩn cấp...'])
      addToast('info', 'Dừng tác vụ', 'Đang gửi lệnh dừng tiến trình cào truyện...')
    } catch (err: any) {
      console.warn('Cancel error:', err)
    }
  }

  const [inAppUrl, setInAppUrl] = useState<BrowserUrlData | null>(null)

  const handleOpenFolder = async (folderPath?: string) => {
    try {
      const target = folderPath || 'output'
      await window.api.shell.openPath(target)
    } catch (err: any) {
      addToast('warning', 'Không thể mở thư mục', err.message || 'Thư mục không tồn tại.')
    }
  }

  const handleOpenExternal = async (linkUrl?: string) => {
    if (linkUrl) {
      setInAppUrl({ url: linkUrl, title: 'Xem trang truyện' })
    }
  }

  const handleCopyLogs = () => {
    if (logs.length === 0) return
    navigator.clipboard.writeText(logs.join('\n'))
    addToast('success', 'Đã sao chép', 'Đã copy toàn bộ log vào clipboard.')
  }

  const getLogClass = (logText: string) => {
    if (logText.includes('❌') || logText.includes('[ERROR]') || logText.includes('Thất bại')) {
      return 'text-rose-400 font-medium'
    }
    if (logText.includes('⚠️') || logText.includes('[WARN]') || logText.includes('cảnh báo')) {
      return 'text-amber-300'
    }
    if (logText.includes('✅') || logText.includes('🎉') || logText.includes('thành công') || logText.includes('HOÀN TẤT')) {
      return 'text-emerald-400 font-semibold'
    }
    if (logText.includes('🔍') || logText.includes('📄') || logText.includes('🌐') || logText.includes('🚀') || logText.includes('🔑')) {
      return 'text-sky-300'
    }
    return 'text-slate-200'
  }

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden bg-slate-50 text-slate-800 select-none">
      {/* Toast Notification Container */}
      <div className="fixed top-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto p-4 rounded-xl shadow-lg border flex items-start gap-3 transition-all duration-200 animate-in fade-in slide-in-from-top-2 ${
              t.type === 'success'
                ? 'bg-white border-emerald-200 text-slate-800 shadow-emerald-500/10'
                : t.type === 'error'
                  ? 'bg-white border-rose-200 text-slate-800 shadow-rose-500/10'
                  : t.type === 'warning'
                    ? 'bg-white border-amber-200 text-slate-800 shadow-amber-500/10'
                    : 'bg-white border-indigo-200 text-slate-800 shadow-indigo-500/10'
            }`}
          >
            {t.type === 'success' && <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />}
            {t.type === 'error' && <XCircle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />}
            {t.type === 'warning' && <AlertCircle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />}
            {t.type === 'info' && <Info className="w-5 h-5 text-indigo-500 shrink-0 mt-0.5" />}
            <div className="flex-1">
              <h4 className="text-xs font-bold text-slate-900">{t.title}</h4>
              <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">{t.message}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Top Header Bar */}
      <div className="px-6 py-4 bg-white border-b border-slate-200/80 flex items-center justify-between shrink-0 shadow-sm">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
              <BookOpen className="w-4 h-4" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Cào Truyện & Tự Động Đăng CMS BlogBio
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5 ml-10">
            Cào nội dung chương, dịch thuật sang tiếng Anh, xuất bản bài viết trực tiếp lên hệ thống CMS
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => handleOpenFolder()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition border border-slate-200"
            title="Mở thư mục output"
          >
            <FolderOpen className="w-3.5 h-3.5 text-slate-500" />
            <span>Thư mục Output</span>
          </button>
          <button
            onClick={loadHistory}
            disabled={isLoadingHistory}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition border border-slate-200"
            title="Làm mới lịch sử"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${isLoadingHistory ? 'animate-spin' : ''}`} />
            <span>Làm mới</span>
          </button>
        </div>
      </div>

      {/* Main Content Area: Scrollable */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {/* 1. CONFIG CARD */}
        <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-sm space-y-4">
          {/* URL & Parser Row */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="md:col-span-3">
              <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                URL Trang Truyện (Nguồn cào)
              </label>
              <div className="relative flex items-center">
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="Nhập URL trang truyện (ví dụ: https://...)..."
                  className="w-full pl-9 pr-20 py-2.5 rounded-xl border border-slate-300 bg-slate-50/50 text-sm text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 font-mono transition"
                />
                <Link className="w-4 h-4 text-slate-400 absolute left-3 pointer-events-none" />
                <div className="absolute right-2 flex items-center gap-1">
                  {url && (
                    <button
                      onClick={() => setUrl('')}
                      className="p-1 text-slate-400 hover:text-slate-600 rounded-md transition"
                      title="Xóa URL"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <button
                    onClick={handlePasteUrl}
                    className="flex items-center gap-1 px-2 py-1 text-xs font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-md transition"
                    title="Dán từ Clipboard"
                  >
                    <ClipboardPaste className="w-3.5 h-3.5" />
                    <span>Dán</span>
                  </button>
                </div>
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                Bộ bóc tách (Parser)
              </label>
              <select
                value={parser}
                onChange={(e) => setParser(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl border border-slate-300 bg-slate-50/50 text-sm text-slate-800 focus:bg-white focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition"
              >
                <option value="universal">Tự động nhận diện (Universal)</option>
                <option value="ahcms">AH CMS Parser (fast2tricks)</option>
                <option value="treeiq">TreeIQ Parser (treeiq.biz)</option>
              </select>
            </div>
          </div>

          {/* Options Row (Checkboxes) */}
          <div className="flex flex-wrap items-center gap-6 pt-1 text-sm font-medium text-slate-700">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={downloadImages}
                onChange={(e) => setDownloadImages(e.target.checked)}
                className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300 cursor-pointer"
              />
              <span>Tải hình ảnh</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={translateEn}
                onChange={(e) => setTranslateEn(e.target.checked)}
                className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300 cursor-pointer"
              />
              <span>Dịch sang tiếng Anh (Google Translate)</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={publishCms}
                onChange={(e) => setPublishCms(e.target.checked)}
                className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300 cursor-pointer"
              />
              <span>Tự động đăng CMS BlogBio</span>
            </label>
          </div>

          {/* Chapter Range, Delay & Actions Row */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-slate-100">
            <div className="flex flex-wrap items-center gap-4 text-xs font-semibold text-slate-700">
              <div className="flex items-center gap-2">
                <span>Từ Chapter:</span>
                <input
                  type="number"
                  min={1}
                  value={startCh}
                  onChange={(e) => setStartCh(parseInt(e.target.value) || 1)}
                  className="w-16 px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-center text-slate-800 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div className="flex items-center gap-2">
                <span>Đến Chapter (0 = hết):</span>
                <input
                  type="number"
                  min={0}
                  value={endCh}
                  onChange={(e) => setEndCh(parseInt(e.target.value) || 0)}
                  className="w-16 px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-center text-slate-800 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div className="flex items-center gap-2">
                <span>Nghỉ (giây):</span>
                <input
                  type="number"
                  min={0.1}
                  step={0.5}
                  value={delay}
                  onChange={(e) => setDelay(parseFloat(e.target.value) || 1.0)}
                  className="w-16 px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-center text-slate-800 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <button
                disabled={isScraping || !url.trim()}
                onClick={handleStartScraping}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition shadow-md shadow-indigo-600/20 active:scale-95"
              >
                {isScraping ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4 fill-white" />
                )}
                <span>{isScraping ? 'Đang cào truyện...' : 'Bắt Đầu Cào Truyện'}</span>
              </button>

              <button
                disabled={!isScraping}
                onClick={handleCancelScraping}
                className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-semibold bg-rose-50 text-rose-600 hover:bg-rose-100 disabled:opacity-40 disabled:hover:bg-rose-50 transition border border-rose-200"
              >
                <Square className="w-3.5 h-3.5 fill-rose-600" />
                <span>Dừng lại</span>
              </button>
            </div>
          </div>
        </div>

        {/* 2. CMS CONFIG CARD (MULTI-SITE SUPPORT: BLOGBIO & TREEIQ) */}
        {publishCms && (
          <div className="bg-white rounded-2xl border border-slate-200/90 p-4 shadow-sm space-y-3 transition-all">
            <div className="flex flex-wrap items-center justify-between border-b border-slate-100 pb-2.5 gap-2">
              <div className="flex items-center gap-2">
                <Settings2 className="w-4 h-4 text-indigo-600" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                  Cấu Hình CMS Đăng Bài Báo
                </h3>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-slate-400 font-semibold mr-1">Preset nhanh:</span>
                <button
                  type="button"
                  onClick={() => {
                    setCmsUrl('https://vmnewstoryus.cfx.bz')
                    setCmsUser('admin')
                    setCmsPass('')
                    addToast('info', 'Chọn site cũ', 'Đã nạp thông tin site BlogBio: vmnewstoryus.cfx.bz')
                  }}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition ${
                    cmsUrl.includes('cfx.bz')
                      ? 'bg-indigo-50 border-indigo-300 text-indigo-700 shadow-xs'
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
                    addToast('info', 'Chọn site mới', 'Đã nạp thông tin site TreeIQ: vmstoryab.teasy.live')
                  }}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition ${
                    cmsUrl.includes('teasy.live')
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-700 shadow-xs'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Site 2: vmstoryab (TreeIQ)
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  CMS Base URL
                </label>
                <input
                  type="text"
                  value={cmsUrl}
                  onChange={(e) => setCmsUrl(e.target.value)}
                  placeholder="https://vmstoryab.teasy.live"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 bg-slate-50/50 text-xs text-slate-800 font-mono focus:bg-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Tài khoản CMS (Email/User)
                </label>
                <input
                  type="text"
                  value={cmsUser}
                  onChange={(e) => setCmsUser(e.target.value)}
                  placeholder="vinhmai@teasy.live"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 bg-slate-50/50 text-xs text-slate-800 font-mono focus:bg-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Mật khẩu CMS
                </label>
                <div className="relative flex items-center">
                  <input
                    type={showCmsPass ? 'text' : 'password'}
                    value={cmsPass}
                    onChange={(e) => setCmsPass(e.target.value)}
                    placeholder="••••••••"
                    className="w-full px-3 py-2 pr-9 rounded-xl border border-slate-300 bg-slate-50/50 text-xs text-slate-800 font-mono focus:bg-white focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCmsPass(!showCmsPass)}
                    className="absolute right-2.5 text-slate-400 hover:text-slate-600 p-0.5"
                  >
                    {showCmsPass ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
              <div className="flex items-center gap-2">
                <button
                  disabled={isTestingCms}
                  onClick={handleTestCms}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition border border-slate-200"
                >
                  <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${isTestingCms ? 'animate-spin' : ''}`} />
                  <span>{isTestingCms ? 'Đang kiểm tra...' : 'Kiểm Tra Kết Nối'}</span>
                </button>

                <button
                  onClick={handleSaveCmsConfig}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 transition border border-indigo-200"
                >
                  <span>Lưu Cấu Hình Này</span>
                </button>
              </div>

              <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
                <span>Nền tảng phát hiện:</span>
                <span className="font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-100">
                  {cmsUrl.includes('teasy.live') || cmsUrl.includes('treeiq')
                    ? 'TreeIQ CMS Network'
                    : 'BlogBio (Laravel API)'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* 3. PROGRESS BAR (IF RUNNING OR JUST COMPLETED) */}
        {(isScraping || progressPct > 0) && (
          <div className="bg-white rounded-2xl border border-slate-200/90 p-4 shadow-sm space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold">
              <span className="text-slate-700">{progressStatus || 'Đang thực thi...'}</span>
              <span className="text-indigo-600 font-mono">{progressPct}%</span>
            </div>
            <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200/60">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-full transition-all duration-300"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        )}

        {/* 4. SPLIT LAYOUT: CONSOLE LOG & SCRAPED HISTORY TABLE */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Real-time Terminal Log */}
          <div className="bg-slate-950 border border-slate-900 rounded-2xl flex flex-col h-[380px] shadow-md overflow-hidden font-mono">
            <div className="px-4 py-2.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-semibold text-slate-200">
                  Nhật Ký Thực Thi (Real-time Log)
                </span>
                <span className="text-[10px] text-slate-500">({logs.length} dòng)</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setAutoScroll(!autoScroll)}
                  className={`text-[10px] px-2 py-0.5 rounded transition ${
                    autoScroll ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/30' : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Tự động cuộn theo log mới"
                >
                  Cuộn: {autoScroll ? 'Bật' : 'Tắt'}
                </button>
                <button
                  onClick={handleCopyLogs}
                  disabled={logs.length === 0}
                  className="p-1 text-slate-400 hover:text-slate-200 disabled:opacity-30 transition"
                  title="Sao chép toàn bộ log"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setLogs([])}
                  disabled={logs.length === 0}
                  className="p-1 text-slate-400 hover:text-rose-400 disabled:opacity-30 transition"
                  title="Xóa nhật ký"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <div
              ref={logContainerRef}
              className="flex-1 p-3.5 overflow-y-auto space-y-1 text-xs select-text"
            >
              {logs.length === 0 ? (
                <p className="text-slate-600 italic">Hệ thống sẵn sàng. Nhấn Bắt Đầu Cào Truyện để chạy...</p>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className={`leading-relaxed break-all ${getLogClass(log)}`}>
                    {log}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Lịch Sử Truyện Đã Cào (History Table) */}
          <div className="bg-white border border-slate-200/90 rounded-2xl flex flex-col h-[380px] shadow-sm overflow-hidden">
            <div className="px-4 py-2.5 border-b border-slate-100 flex items-center justify-between shrink-0 bg-slate-50/50">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-600" />
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                  Lịch Sử Truyện Đã Cào
                </h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                  {historyItems.length}
                </span>
              </div>

              <span className="text-[11px] text-slate-400 italic">
                Nhấp đúp dòng để mở thư mục
              </span>
            </div>

            <div className="flex-1 overflow-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 sticky top-0 border-b border-slate-200/70 font-semibold z-10">
                  <tr>
                    <th className="py-2.5 px-3 w-10 text-center">ID</th>
                    <th className="py-2.5 px-3">Tên Truyện</th>
                    <th className="py-2.5 px-2 text-center w-16">Chương</th>
                    <th className="py-2.5 px-2 text-center w-16">Dịch EN</th>
                    <th className="py-2.5 px-2 text-center w-16">Đăng CMS</th>
                    <th className="py-2.5 px-3 text-right w-20">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {historyItems.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-16 text-center text-slate-400 italic">
                        Chưa có lịch sử truyện nào được cào.
                      </td>
                    </tr>
                  ) : (
                    historyItems.map((item) => (
                      <tr
                        key={item.id}
                        onDoubleClick={() => handleOpenFolder(item.output_dir)}
                        className="hover:bg-slate-50 transition cursor-pointer group"
                      >
                        <td className="py-2.5 px-3 text-center text-slate-400 font-mono text-[11px]">
                          {item.id}
                        </td>
                        <td className="py-2.5 px-3 max-w-[160px] truncate" title={item.url}>
                          <p className="font-semibold text-slate-800 truncate">{item.title || 'Untitled'}</p>
                          <p className="text-[10px] text-slate-400 truncate">{item.output_dir || ''}</p>
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          <span className="px-2 py-0.5 rounded-full font-mono text-[11px] font-semibold bg-indigo-50 text-indigo-600 border border-indigo-100">
                            {item.chapters_count || 0}
                          </span>
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          {item.translated ? (
                            <span className="text-emerald-600 font-bold">✅</span>
                          ) : (
                            <span className="text-slate-300">❌</span>
                          )}
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          {item.published ? (
                            <span className="text-emerald-600 font-bold">✅</span>
                          ) : (
                            <span className="text-slate-300">❌</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-1 opacity-80 group-hover:opacity-100">
                            {item.output_dir && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleOpenFolder(item.output_dir)
                                }}
                                className="p-1 text-slate-400 hover:text-indigo-600 rounded transition"
                                title="Mở thư mục"
                              >
                                <FolderOpen className="w-3.5 h-3.5" />
                              </button>
                            )}
                            {item.url && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleOpenExternal(item.url)
                                }}
                                className="p-1 text-slate-400 hover:text-indigo-600 rounded transition"
                                title="Mở URL gốc"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* In-App Browser Modal (Opens links directly in app; opening another link automatically ends previous link) */}
      <InAppBrowserModal urlItem={inAppUrl} onClose={() => setInAppUrl(null)} />
    </div>
  )
}

export default CaoTruyenPage
