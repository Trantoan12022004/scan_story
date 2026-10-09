import React, { useState, useEffect } from 'react'
import {
  Download,
  FileVideo,
  Trash2,
  FolderOpen
} from 'lucide-react'
import { DownloadedItem } from '../types'

export const TaiReelsPage: React.FC = () => {
  const [url, setUrl] = useState('')
  const [isDownloading, setIsDownloading] = useState(false)
  const [progress, setProgress] = useState<any>(null)
  const [history, setHistory] = useState<DownloadedItem[]>([])

  const loadHistory = async () => {
    try {
      const list = await window.api.db.getDownloadedVideos(50)
      setHistory(list || [])
    } catch {}
  }

  useEffect(() => {
    loadHistory()

    const unsub = window.api.fb.onProgress((p) => {
      setProgress(p)
      if (p.status === 'finished') {
        setIsDownloading(false)
        loadHistory()
      }
    })
    return () => unsub()
  }, [])

  const handleDownload = async () => {
    const cleanUrl = url.trim()
    if (!cleanUrl) {
      alert('Vui lòng nhập link video hoặc Facebook Reel.')
      return
    }

    setIsDownloading(true)
    setProgress({ percent: 0, status: 'downloading', speed: '', eta: '' })

    try {
      const settings = await window.api.db.getSettings()
      const targetDir = settings.video_dir || 'C:\\Users\\Trant\\Videos\\Seedance\\anhtonton\\AI_VIDEO'
      const fileName = `fb_${Date.now()}.mp4`
      const outputPath = `${targetDir}\\${fileName}`

      const meta = await window.api.fb.getMetadata(cleanUrl)
      const res = await window.api.fb.download(cleanUrl, outputPath)

      if (res.success) {
        await window.api.db.addDownloadedVideo({
          url: cleanUrl,
          title: meta?.title || fileName,
          duration: meta?.duration ? `${Math.round(meta.duration)}s` : '',
          file_path: res.filePath
        })
        setUrl('')
        loadHistory()
      } else {
        alert(`Tải video thất bại: ${res.error}`)
      }
    } catch (err: any) {
      alert(`Lỗi hệ thống: ${err.message}`)
    } finally {
      setIsDownloading(false)
    }
  }

  const handleDeleteHistory = async (id?: number) => {
    if (!id) return
    await window.api.db.deleteDownloadedVideo(id)
    loadHistory()
  }

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden bg-slate-50 text-slate-800 p-6 space-y-5">
      {/* Page Header */}
      <div>
        <h2 className="text-lg font-bold tracking-tight text-slate-900 flex items-center gap-2">
          <Download className="w-5 h-5 text-indigo-600" />
          <span>Tải Video Facebook & Reels</span>
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Hỗ trợ tải video chất lượng cao nhất bằng yt-dlp tích hợp sẵn
        </p>
      </div>

      {/* Download Input Card */}
      <div className="p-5 rounded-2xl bg-white border border-slate-200/90 space-y-4 shadow-sm">
        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
          Đường dẫn video (Facebook Reel / Watch / Post)
        </label>
        <div className="flex gap-3">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.facebook.com/reel/123456789 hoặc https://fb.watch/..."
            className="flex-1 rounded-xl bg-slate-50 border border-slate-300 px-4 py-2.5 text-xs text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
          />
          <button
            disabled={isDownloading || !url.trim()}
            onClick={handleDownload}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-indigo-600/20 active:scale-95 transition"
          >
            <Download className="w-4 h-4" />
            <span>{isDownloading ? 'Đang tải...' : 'Tải ngay'}</span>
          </button>
        </div>

        {/* Live Progress Bar */}
        {progress && isDownloading && (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-700">
              <span className="font-bold text-indigo-600">
                Tiến độ: {Math.round(progress.percent || 0)}%
              </span>
              <span className="text-slate-500">
                {progress.speed && `Tốc độ: ${progress.speed}`} {progress.eta && `• Còn lại: ${progress.eta}`}
              </span>
            </div>
            <div className="w-full h-2 rounded-full bg-slate-200 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-indigo-600 transition-all duration-150"
                style={{ width: `${progress.percent || 0}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Download History Table */}
      <div className="flex-1 flex flex-col bg-white border border-slate-200/90 rounded-2xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
            <FileVideo className="w-4 h-4 text-indigo-600" />
            <span>Lịch sử tải xuống gần đây ({history.length})</span>
          </h3>
        </div>

        <div className="flex-1 overflow-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="sticky top-0 bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200 text-[11px]">
              <tr>
                <th className="py-2.5 px-4 w-12 text-center">#</th>
                <th className="py-2.5 px-4">Tiêu đề video</th>
                <th className="py-2.5 px-4 w-28">Thời lượng</th>
                <th className="py-2.5 px-4 w-64">Đường dẫn file</th>
                <th className="py-2.5 px-4 w-28 text-center">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {history.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-400 italic">
                    Chưa có video nào được tải về
                  </td>
                </tr>
              ) : (
                history.map((it, idx) => (
                  <tr key={it.id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 text-center font-mono text-slate-400">{idx + 1}</td>
                    <td className="py-3 px-4 font-semibold text-slate-800">
                      <div className="truncate max-w-sm" title={it.title}>
                        {it.title || 'Video Facebook'}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-500 font-mono">{it.duration || '-'}</td>
                    <td className="py-3 px-4 text-slate-500 font-mono text-[11px] truncate max-w-xs" title={it.file_path}>
                      {it.file_path || '-'}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <div className="flex items-center justify-center gap-2">
                        {it.file_path && (
                          <button
                            onClick={() => window.api.shell.openPath(it.file_path!)}
                            className="p-1 rounded-lg text-slate-400 hover:text-indigo-600 transition"
                            title="Mở thư mục"
                          >
                            <FolderOpen className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteHistory(it.id)}
                          className="p-1 rounded-lg text-slate-400 hover:text-rose-600 transition"
                          title="Xóa"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
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
  )
}
