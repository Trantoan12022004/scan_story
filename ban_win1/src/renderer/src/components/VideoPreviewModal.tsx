import React, { useState, useEffect } from 'react'
import { X, Copy, Check, Film, AlertTriangle, RefreshCw, ExternalLink, FolderOpen } from 'lucide-react'

export interface PreviewVideoData {
  stt: string
  title: string
  path?: string
  url?: string
  type: 'sample' | 'new'
}

interface VideoPreviewModalProps {
  video: PreviewVideoData | null
  onClose: () => void
}

export const VideoPreviewModal: React.FC<VideoPreviewModalProps> = ({ video, onClose }) => {
  const [copied, setCopied] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [streamSrc, setStreamSrc] = useState<string>('')
  const [candidateIndex, setCandidateIndex] = useState<number>(0)
  const [candidates, setCandidates] = useState<string[]>([])

  useEffect(() => {
    let active = true
    setHasError(false)
    setCopied(false)
    setIsLoading(true)
    setCandidateIndex(0)

    const initSources = async () => {
      if (!video) {
        if (active) {
          setStreamSrc('')
          setCandidates([])
          setIsLoading(false)
        }
        return
      }

      if (video.path) {
        const cleanPath = video.path.replace(/\\/g, '/')
        let httpUrl = ''
        if (window.api?.video?.getStreamUrl) {
          try {
            httpUrl = await window.api.video.getStreamUrl(video.path)
          } catch {}
        }

        // Three independent layers to guarantee playback:
        // 1. Direct HTTP Range streaming from local MediaServer (gold standard, handles moov at end of file)
        // 2. Direct native file URL file:/// (native Chromium file reader, range supported)
        // 3. Custom scheme media-file://
        const sourceList: string[] = []
        if (httpUrl) sourceList.push(httpUrl)
        sourceList.push(`file:///${cleanPath}`)
        sourceList.push(`media-file://video?path=${encodeURIComponent(video.path)}`)

        if (active) {
          setCandidates(sourceList)
          setStreamSrc(sourceList[0] || '')
          setIsLoading(false)
        }
      } else if (video.url) {
        if (active) {
          setCandidates([video.url])
          setStreamSrc(video.url)
          setIsLoading(false)
        }
      } else {
        if (active) {
          setCandidates([])
          setStreamSrc('')
          setIsLoading(false)
        }
      }
    }

    initSources()
    return () => {
      active = false
    }
  }, [video?.path, video?.url, video?.stt])

  if (!video) return null

  const handleVideoError = () => {
    const nextIdx = candidateIndex + 1
    if (nextIdx < candidates.length) {
      console.warn(`[VideoPreview] Source failed (${streamSrc}), trying fallback #${nextIdx}:`, candidates[nextIdx])
      setCandidateIndex(nextIdx)
      setStreamSrc(candidates[nextIdx])
    } else {
      console.error('[VideoPreview] All playback sources exhausted for:', video.path || video.url)
      setHasError(true)
    }
  }

  const handleCopyPath = () => {
    const textToCopy = video.path || video.url || ''
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleOpenExternal = async () => {
    if (video.path) {
      if (window.api?.shell?.playFile) {
        await window.api.shell.playFile(video.path)
      } else {
        await window.api.shell.openPath(video.path)
      }
    } else if (video.url) {
      window.api.shell.openExternal(video.url)
    }
  }

  const handleShowInFolder = async () => {
    if (video.path) {
      await window.api.shell.openPath(video.path)
    }
  }

  const handleRetry = () => {
    setHasError(false)
    setCandidateIndex(0)
    if (candidates.length > 0) {
      setStreamSrc(candidates[0])
    }
  }

  const isSample = video.type === 'sample'

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-xl shadow-2xl flex flex-col overflow-hidden text-slate-100">
        {/* Header */}
        <div className="px-4 py-3 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5 truncate">
            <span
              className={`px-2 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wider ${
                isSample
                  ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                  : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
              }`}
            >
              #{video.stt} {isSample ? 'Video Mẫu' : 'Video Mới'}
            </span>
            <span className="text-xs font-semibold text-slate-300 truncate max-w-[240px]" title={video.title}>
              {video.title}
            </span>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {/* Open in external player button */}
            {video.path && (
              <button
                onClick={handleOpenExternal}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700 transition"
                title="Mở bằng trình phát ngoài (VLC/Media Player)"
              >
                <ExternalLink className="w-3.5 h-3.5 text-indigo-400" />
                <span className="text-[11px]">Mở ngoài</span>
              </button>
            )}

            {/* Copy path button */}
            <button
              onClick={handleCopyPath}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-200 hover:bg-slate-700 hover:text-white border border-slate-700 transition"
              title="Sao chép đường dẫn file video"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-indigo-400" />}
              <span className="text-[11px]">{copied ? 'Đã sao chép' : 'Sao chép đường dẫn'}</span>
            </button>

            {/* Close button */}
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Đóng xem trước"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Video Player */}
        <div className="bg-black flex items-center justify-center relative min-h-[260px] max-h-[460px]">
          {isLoading ? (
            <div className="p-8 text-center text-slate-400 flex flex-col items-center">
              <RefreshCw className="w-8 h-8 animate-spin text-indigo-400 mb-2" />
              <p className="text-xs">Đang tải luồng video...</p>
            </div>
          ) : hasError ? (
            <div className="p-8 text-center text-slate-400 max-w-sm flex flex-col items-center">
              <AlertTriangle className="w-10 h-10 text-amber-400 mb-2.5" />
              <p className="text-sm font-semibold text-slate-200 mb-1">Không thể phát trực tiếp video này</p>
              <p className="text-xs text-slate-400 mb-4">
                Định dạng codec chưa tương thích với trình phát tích hợp hoặc file đang bị khóa bởi ứng dụng khác.
              </p>
              <div className="flex flex-wrap items-center justify-center gap-2">
                <button
                  onClick={handleRetry}
                  className="px-3 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Thử lại</span>
                </button>
                {video.path && (
                  <button
                    onClick={handleOpenExternal}
                    className="px-3 py-1.5 rounded-lg text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-medium flex items-center gap-1.5 transition"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Mở bằng trình phát ngoài</span>
                  </button>
                )}
                {video.path && (
                  <button
                    onClick={handleShowInFolder}
                    className="px-3 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition"
                  >
                    <FolderOpen className="w-3.5 h-3.5" />
                    <span>Mở thư mục</span>
                  </button>
                )}
              </div>
            </div>
          ) : streamSrc ? (
            <video
              key={streamSrc} // Changing key automatically terminates previous video playback!
              src={streamSrc}
              controls
              autoPlay
              playsInline
              preload="auto"
              onError={handleVideoError}
              onCanPlay={() => setHasError(false)}
              className="w-full max-h-[460px] object-contain focus:outline-none"
            >
              Trình duyệt không hỗ trợ phát video định dạng này.
            </video>
          ) : (
            <div className="p-8 text-center text-slate-500">
              <Film className="w-10 h-10 mx-auto mb-2 opacity-40 text-slate-400" />
              <p className="text-xs">Không tìm thấy đường dẫn video hợp lệ.</p>
            </div>
          )}
        </div>

        {/* Footer info bar */}
        <div className="px-4 py-2 bg-slate-950/60 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
          <span className="truncate max-w-[420px] font-mono text-[10px] text-slate-400" title={video.path || video.url}>
            📁 {video.path || video.url || 'Chưa có file'}
          </span>
          <span className="text-[10px] text-slate-500">Bấm Esc hoặc ✕ để thoát</span>
        </div>
      </div>
    </div>
  )
}



