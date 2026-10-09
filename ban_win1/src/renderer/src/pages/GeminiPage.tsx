import React, { useState, useEffect, useRef } from 'react'
import {
  Sparkles,
  Bot,
  Copy,
  Check,
  RotateCw,
  Plus,
  Trash2,
  Video
} from 'lucide-react'
import { PromptItem, VideoItem } from '../types'

export const GeminiPage: React.FC = () => {
  const [prompts, setPrompts] = useState<PromptItem[]>([])
  const [selectedPrompt, setSelectedPrompt] = useState<PromptItem | null>(null)
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [videos, setVideos] = useState<VideoItem[]>([])
  const [selectedVideoStt, setSelectedVideoStt] = useState<string>('')
  const [copiedSample, setCopiedSample] = useState(false)

  // New prompt input state
  const [isAdding, setIsAdding] = useState(false)
  const [newName, setNewName] = useState('')
  const [newContent, setNewContent] = useState('')

  const webviewRef = useRef<any>(null)

  const loadPrompts = async () => {
    try {
      const list = await window.api.db.getPrompts()
      setPrompts(list || [])
      if (list && list.length > 0 && !selectedPrompt) {
        setSelectedPrompt(list[0])
      }
    } catch {}
  }

  const loadVideos = async () => {
    try {
      const vids = await window.api.db.getVideos()
      setVideos(vids || [])
      if (vids && vids.length > 0) {
        setSelectedVideoStt(vids[0].stt)
      }
    } catch {}
  }

  useEffect(() => {
    loadPrompts()
    loadVideos()
  }, [])

  const handleCopyPrompt = (prompt: PromptItem) => {
    if (prompt?.content) {
      navigator.clipboard.writeText(prompt.content)
      setCopiedId(prompt.id || 0)
      setTimeout(() => setCopiedId(null), 2000)
    }
  }

  const handleCopySampleVideoPath = async () => {
    try {
      const settings = await window.api.db.getSettings()
      const sampleDir = settings.sample_video_dir || 'C:\\Users\\Trant\\Videos\\short_drama'
      const samplePath = `${sampleDir}\\${selectedVideoStt}.mp4`
      navigator.clipboard.writeText(samplePath)
      setCopiedSample(true)
      setTimeout(() => setCopiedSample(false), 2000)
    } catch {
      alert('Không thể sao chép đường dẫn video mẫu.')
    }
  }

  const handleSaveNewPrompt = async () => {
    if (!newName.trim() || !newContent.trim()) {
      alert('Vui lòng nhập tên và nội dung prompt.')
      return
    }

    await window.api.db.savePrompt(newName.trim(), newContent.trim())
    setNewName('')
    setNewContent('')
    setIsAdding(false)
    loadPrompts()
  }

  const handleDeletePrompt = async (id?: number) => {
    if (!id) return
    if (confirm('Xóa prompt này khỏi thư viện?')) {
      await window.api.db.deletePrompt(id)
      loadPrompts()
    }
  }

  const handleReloadWebview = () => {
    if (webviewRef.current) {
      webviewRef.current.reload()
    }
  }

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden bg-slate-50 text-slate-800">
      {/* Top Header Controls Bar */}
      <div className="px-6 py-3.5 bg-white border-b border-slate-200/80 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 border border-purple-100 flex items-center justify-center">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight">
              Gemini AI Studio (Native Chromium Integration)
            </h2>
            <p className="text-[11px] text-slate-500">
              Đăng nhập tài khoản Google an toàn 100% • Tự động gắn đường dẫn Video mẫu (short_drama)
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          {/* Quick Select Video for Sample video injection */}
          <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5">
            <Video className="w-3.5 h-3.5 text-indigo-600" />
            <span className="text-xs text-slate-500 font-semibold">Video mẫu:</span>
            <select
              value={selectedVideoStt}
              onChange={(e) => setSelectedVideoStt(e.target.value)}
              className="bg-transparent text-xs font-semibold text-slate-800 focus:outline-none"
            >
              {videos.map((v) => (
                <option key={v.stt} value={v.stt}>
                  #{v.stt} ({v.bao_moi || v.stt + '.mp4'})
                </option>
              ))}
            </select>
            <button
              onClick={handleCopySampleVideoPath}
              className="ml-1 px-2 py-0.5 rounded-lg text-[11px] font-semibold bg-indigo-600 text-white hover:bg-indigo-700 transition flex items-center gap-1 shadow-sm active:scale-95"
              title="Sao chép đường dẫn video mẫu để dán vào Gemini"
            >
              {copiedSample ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
              <span>{copiedSample ? 'Đã chép!' : 'Chép link'}</span>
            </button>
          </div>

          <button
            onClick={handleReloadWebview}
            className="p-2 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-slate-900 transition"
            title="Tải lại Gemini"
          >
            <RotateCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Split Body: Left Prompt Library & Right Webview */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Prompt Library Sidebar */}
        <div className="w-80 border-r border-slate-200/80 bg-white flex flex-col justify-between overflow-hidden shadow-sm">
          <div className="p-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
              <Bot className="w-4 h-4 text-purple-600" />
              <span>Prompt Mẫu ({prompts.length})</span>
            </span>
            <button
              onClick={() => setIsAdding(!isAdding)}
              className="p-1 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition"
              title="Thêm prompt mới"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>

          {/* New Prompt Input Box */}
          {isAdding && (
            <div className="p-3 border-b border-slate-100 bg-slate-50 space-y-2">
              <input
                type="text"
                placeholder="Tên prompt..."
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1 text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
              />
              <textarea
                rows={3}
                placeholder="Nội dung prompt..."
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
              />
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setIsAdding(false)}
                  className="px-2 py-1 text-[11px] text-slate-500 hover:text-slate-700"
                >
                  Hủy
                </button>
                <button
                  onClick={handleSaveNewPrompt}
                  className="px-3 py-1 text-[11px] font-semibold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  Lưu
                </button>
              </div>
            </div>
          )}

          {/* Prompts List */}
          <div className="flex-1 overflow-auto divide-y divide-slate-100 p-2 space-y-1">
            {prompts.map((p) => {
              const isSelected = selectedPrompt?.id === p.id
              return (
                <div
                  key={p.id}
                  onClick={() => setSelectedPrompt(p)}
                  className={`p-2.5 rounded-xl cursor-pointer transition flex flex-col gap-1.5 ${
                    isSelected ? 'bg-indigo-50 border border-indigo-200' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-800">{p.name}</span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleCopyPrompt(p)
                        }}
                        className="p-1 rounded-md text-slate-400 hover:text-indigo-600 hover:bg-slate-100 transition"
                        title="Sao chép prompt"
                      >
                        {copiedId === p.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDeletePrompt(p.id)
                        }}
                        className="p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-slate-100 transition"
                        title="Xóa prompt"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                    {p.content}
                  </p>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right: Embedded Webview Container */}
        <div className="flex-1 h-full relative bg-slate-100 flex flex-col">
          {/* @ts-ignore: Electron webview tag */}
          <webview
            ref={webviewRef}
            src="https://gemini.google.com/app"
            style={{ width: '100%', height: '100%' }}
            useragent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            allowpopups={true}
          />
        </div>
      </div>
    </div>
  )
}
