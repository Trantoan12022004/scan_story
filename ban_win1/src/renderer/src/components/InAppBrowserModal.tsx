import React, { useState, useRef, useEffect } from 'react'
import {
  X,
  Copy,
  Check,
  RotateCw,
  ExternalLink,
  ShieldCheck,
  Globe,
  ChevronLeft,
  ChevronRight,
  Loader2
} from 'lucide-react'
import { cleanRedirectUrl, generateInAppBrowserScript } from '../lib/url-helper'

export interface BrowserUrlData {
  url: string
  title?: string
}

interface InAppBrowserModalProps {
  urlItem: BrowserUrlData | null
  onClose: () => void
}

export const InAppBrowserModal: React.FC<InAppBrowserModalProps> = ({ urlItem, onClose }) => {
  const [copied, setCopied] = useState(false)
  const [canGoBack, setCanGoBack] = useState(false)
  const [canGoForward, setCanGoForward] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [currentUrl, setCurrentUrl] = useState(urlItem?.url || '')
  const [inputUrl, setInputUrl] = useState(urlItem?.url || '')
  const [currentTitle, setCurrentTitle] = useState(urlItem?.title || '')
  const [isEditingUrl, setIsEditingUrl] = useState(false)

  const webviewRef = useRef<any>(null)

  // Reset local states when urlItem prop changes
  useEffect(() => {
    if (urlItem?.url) {
      setCurrentUrl(urlItem.url)
      setInputUrl(urlItem.url)
      setCurrentTitle(urlItem.title || '')
      setCanGoBack(false)
      setCanGoForward(false)
      setIsLoading(false)
    }
  }, [urlItem?.url])

  // Attach navigation & child link listeners to webview
  useEffect(() => {
    const webview = webviewRef.current
    if (!webview || !urlItem?.url) return

    const injectInterceptorScript = () => {
      try {
        if (typeof webview.executeJavaScript === 'function') {
          webview.executeJavaScript(generateInAppBrowserScript()).catch(() => { })
        }
      } catch { }
    }

    const syncNav = () => {
      try {
        if (typeof webview.canGoBack === 'function') {
          setCanGoBack(webview.canGoBack())
        }
        if (typeof webview.canGoForward === 'function') {
          setCanGoForward(webview.canGoForward())
        }
        if (typeof webview.getURL === 'function') {
          const url = webview.getURL()
          if (url && url !== 'about:blank') {
            setCurrentUrl(url)
            setInputUrl((prev) => (isEditingUrl ? prev : url))
          }
        }
        if (typeof webview.getTitle === 'function') {
          const title = webview.getTitle()
          if (title) setCurrentTitle(title)
        }
      } catch {
        // Ignore if webview is busy or destroyed
      }
    }

    const handleNavigate = (e: any) => {
      if (e.url) {
        setCurrentUrl(e.url)
        setInputUrl((prev) => (isEditingUrl ? prev : e.url))
      }
      syncNav()
      injectInterceptorScript()
    }

    const handleTitle = (e: any) => {
      if (e.title) setCurrentTitle(e.title)
    }

    const handleStartLoading = () => setIsLoading(true)
    const handleStopLoading = () => {
      setIsLoading(false)
      syncNav()
      injectInterceptorScript()
    }

    // Intercept clicks on links that open in new windows / target="_blank"
    const handleNewWindow = (e: any) => {
      e.preventDefault?.()
      if (e.url) {
        const cleaned = cleanRedirectUrl(e.url)
        try {
          webview.loadURL(cleaned)
        } catch { }
      }
    }

    // Intercept in-page redirection shims before Facebook warning interstitial
    const handleWillNavigate = (e: any) => {
      const cleaned = cleanRedirectUrl(e.url)
      if (cleaned !== e.url) {
        e.preventDefault?.()
        try {
          webview.loadURL(cleaned)
        } catch { }
      }
    }

    // Intercept message sent from injected capture script inside the guest page
    const handleConsoleMessage = (e: any) => {
      if (e.message && e.message.startsWith('__BANWIN_NAVIGATE__:')) {
        const target = e.message.slice('__BANWIN_NAVIGATE__:'.length).trim()
        if (target) {
          const cleaned = cleanRedirectUrl(target)
          try {
            webview.loadURL(cleaned)
          } catch { }
        }
      }
    }

    const handleDomReady = () => {
      syncNav()
      injectInterceptorScript()
    }

    const handleFrameFinishLoad = () => {
      injectInterceptorScript()
    }

    webview.addEventListener('did-navigate', handleNavigate)
    webview.addEventListener('did-navigate-in-page', handleNavigate)
    webview.addEventListener('page-title-updated', handleTitle)
    webview.addEventListener('did-start-loading', handleStartLoading)
    webview.addEventListener('did-stop-loading', handleStopLoading)
    webview.addEventListener('dom-ready', handleDomReady)
    webview.addEventListener('did-frame-finish-load', handleFrameFinishLoad)
    webview.addEventListener('console-message', handleConsoleMessage)
    webview.addEventListener('new-window', handleNewWindow)
    webview.addEventListener('will-navigate', handleWillNavigate)

    // Periodically re-ensure interceptor is injected for dynamic comment threads
    const intervalId = setInterval(injectInterceptorScript, 2000)

    return () => {
      clearInterval(intervalId)
      webview.removeEventListener('did-navigate', handleNavigate)
      webview.removeEventListener('did-navigate-in-page', handleNavigate)
      webview.removeEventListener('page-title-updated', handleTitle)
      webview.removeEventListener('did-start-loading', handleStartLoading)
      webview.removeEventListener('did-stop-loading', handleStopLoading)
      webview.removeEventListener('dom-ready', handleDomReady)
      webview.removeEventListener('did-frame-finish-load', handleFrameFinishLoad)
      webview.removeEventListener('console-message', handleConsoleMessage)
      webview.removeEventListener('new-window', handleNewWindow)
      webview.removeEventListener('will-navigate', handleWillNavigate)
    }
  }, [urlItem?.url, isEditingUrl])

  if (!urlItem || !urlItem.url) return null

  const handleGoBack = () => {
    if (webviewRef.current && canGoBack) {
      try {
        webviewRef.current.goBack()
      } catch { }
    }
  }

  const handleGoForward = () => {
    if (webviewRef.current && canGoForward) {
      try {
        webviewRef.current.goForward()
      } catch { }
    }
  }

  const handleReload = () => {
    if (webviewRef.current) {
      try {
        webviewRef.current.reload()
      } catch { }
    }
  }

  const handleUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    let target = inputUrl.trim()
    if (!target) return
    if (!target.startsWith('http://') && !target.startsWith('https://')) {
      target = 'https://' + target
    }
    target = cleanRedirectUrl(target)
    if (webviewRef.current) {
      try {
        webviewRef.current.loadURL(target)
      } catch { }
    }
    setIsEditingUrl(false)
  }

  const handleCopy = () => {
    const target = currentUrl || urlItem.url
    navigator.clipboard.writeText(target)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleOpenExternal = () => {
    const target = currentUrl || urlItem.url
    window.api.shell.openExternal(target)
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center p-3 animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-6xl h-[88vh] shadow-2xl flex flex-col overflow-hidden text-slate-100">
        {/* Browser Top Navigation Bar */}
        <div className="px-4 py-2.5 bg-slate-950 border-b border-slate-800 flex items-center justify-between gap-3">
          {/* Back, Forward, Reload & Title */}
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={handleGoBack}
              disabled={!canGoBack}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-slate-400 transition"
              title="Quay lại trang trước"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <button
              onClick={handleGoForward}
              disabled={!canGoForward}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-slate-400 transition"
              title="Tiến tới trang sau"
            >
              <ChevronRight className="w-4 h-4" />
            </button>

            <button
              onClick={handleReload}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Tải lại trang"
            >
              {isLoading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
              ) : (
                <RotateCw className="w-3.5 h-3.5" />
              )}
            </button>

            <div className="flex items-center gap-1.5 ml-2 min-w-0 max-w-[180px] lg:max-w-xs">
              <Globe className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
              <span
                className="text-xs font-semibold text-slate-300 truncate"
                title={currentTitle || urlItem.title || currentUrl}
              >
                {currentTitle || urlItem.title || 'Trình duyệt ứng dụng'}
              </span>
            </div>
          </div>

          {/* Interactive Address Bar */}
          <form
            onSubmit={handleUrlSubmit}
            className="flex-1 max-w-2xl flex items-center gap-2 bg-slate-900 border border-slate-700 focus-within:border-indigo-500/80 rounded-xl px-3 py-1.5 shadow-inner transition"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <input
              type="text"
              value={inputUrl}
              onChange={(e) => {
                setInputUrl(e.target.value)
                setIsEditingUrl(true)
              }}
              onFocus={() => setIsEditingUrl(true)}
              onBlur={() => {
                setIsEditingUrl(false)
                setInputUrl(currentUrl || urlItem.url)
              }}
              className="text-xs font-mono text-slate-200 bg-transparent outline-none w-full truncate placeholder-slate-500"
              placeholder="Nhập hoặc dán địa chỉ web..."
            />
          </form>

          {/* Action Toolbar */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Copy current active URL */}
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-200 hover:bg-slate-700 hover:text-white border border-slate-700 transition active:scale-95"
              title="Sao chép liên kết hiện tại"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5 text-indigo-400" />
              )}
              <span className="text-[11px]">{copied ? 'Đã sao chép' : 'Sao chép'}</span>
            </button>

            {/* Open current active URL in external browser */}
            <button
              onClick={handleOpenExternal}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700 border border-slate-700 transition active:scale-95"
              title="Mở liên kết hiện tại bằng trình duyệt ngoài của máy tính"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="text-[11px]">Mở ngoài</span>
            </button>

            {/* Close button */}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-rose-400 hover:text-white hover:bg-rose-600 transition ml-1"
              title="Đóng trình duyệt"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Webview Content Container */}
        <div className="flex-1 bg-white relative overflow-hidden">
          {/* Subtle top progress bar when loading */}
          {isLoading && (
            <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500 via-sky-400 to-indigo-500 animate-pulse z-10" />
          )}

          {/* @ts-ignore: Electron webview tag */}
          <webview
            ref={webviewRef}
            key={urlItem.url}
            src={urlItem.url}
            style={{ width: '100%', height: '100%' }}
            useragent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            allowpopups={true}
          />
        </div>
      </div>
    </div>
  )
}
