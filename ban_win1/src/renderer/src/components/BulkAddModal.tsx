import React, { useState } from 'react'
import { X, PlusCircle, CheckCircle2, DownloadCloud } from 'lucide-react'

interface BulkAddModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (insertedCount: number) => void
  nextStt: number
}

export const BulkAddModal: React.FC<BulkAddModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  nextStt
}) => {
  const [text, setText] = useState('')
  const [autoDownloadSample, setAutoDownloadSample] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!isOpen) return null

  const rawLines = text.split('\n').map((l) => l.trim()).filter(Boolean)
  const uniqueUrls = Array.from(new Set(rawLines))

  const handleSubmit = async () => {
    if (uniqueUrls.length === 0) return
    setIsSubmitting(true)
    try {
      const inserted = await window.api.db.bulkInsertReels(uniqueUrls, true)
      if (autoDownloadSample && inserted && inserted.length > 0) {
        // Enqueue batch for background sample download
        const queueItems = inserted.map((row) => ({
          stt: row.stt,
          url: row.bai_goc
        }))
        await window.api.sampleQueue.enqueueBatch(queueItems)
      }
      onSuccess(inserted?.length || 0)
      setText('')
      onClose()
    } catch (err: any) {
      alert(`Lỗi khi thêm bài gốc: ${err.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 rounded-2xl w-full max-w-xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-100">
              <PlusCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-slate-900">Thêm hàng loạt bài gốc (Reels)</h3>
              <p className="text-xs text-slate-500">
                Tự động đánh số STT liên tục bắt đầu từ #{nextStt}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              Dán danh sách liên kết Facebook Reels (Mỗi dòng một link)
            </label>
            <textarea
              rows={8}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={`https://www.facebook.com/reel/123456789\nhttps://www.facebook.com/reel/987654321\nhttps://fb.watch/sample`}
              className="w-full rounded-xl bg-slate-50 border border-slate-300 p-3.5 text-xs text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 font-mono"
            />
          </div>

          <div className="flex items-center justify-between text-xs px-1">
            <span className="text-slate-500">
              Phát hiện: <strong className="text-indigo-600">{rawLines.length}</strong> dòng (
              <strong className="text-emerald-600">{uniqueUrls.length}</strong> link hợp lệ không trùng)
            </span>
            <span className="text-slate-400 font-mono">
              STT: #{nextStt} &rarr; #{nextStt + Math.max(0, uniqueUrls.length - 1)}
            </span>
          </div>

          {/* Option: Auto download sample video */}
          <label className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 border border-slate-200 cursor-pointer hover:bg-slate-100/60 transition">
            <input
              type="checkbox"
              checked={autoDownloadSample}
              onChange={(e) => setAutoDownloadSample(e.target.checked)}
              className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300"
            />
            <div className="flex items-center gap-2">
              <DownloadCloud className="w-4 h-4 text-indigo-600" />
              <div>
                <p className="text-xs font-semibold text-slate-800">
                  Tự động quét và tải video mẫu về máy ngay sau khi thêm
                </p>
                <p className="text-[11px] text-slate-400">
                  Lưu vào short_drama/{'{stt}'}.mp4 để phân tích AI
                </p>
              </div>
            </div>
          </label>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-end gap-3 bg-slate-50/60">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
          >
            Hủy bỏ
          </button>
          <button
            disabled={uniqueUrls.length === 0 || isSubmitting}
            onClick={handleSubmit}
            className="flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-indigo-600/20 active:scale-95 transition"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>{isSubmitting ? 'Đang thêm...' : `Thêm ${uniqueUrls.length} bài gốc`}</span>
          </button>
        </div>
      </div>
    </div>
  )
}
