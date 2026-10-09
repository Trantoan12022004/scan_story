import { app, shell, BrowserWindow, protocol, net } from 'electron'
import { join } from 'path'
import { pathToFileURL } from 'url'
import fs from 'fs'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.ico?asset'
import { getDatabaseService } from './services/database'
import { registerIpcHandlers } from './ipc'
import { resolveMediaProtocolPath } from './services/content-generator'
import { MediaServer } from './services/media-server'

// Register privileged custom scheme for seamless local video streaming preview
protocol.registerSchemesAsPrivileged([
  {
    scheme: 'media-file',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      bypassCSP: true,
      corsEnabled: true
    }
  }
])



import { cleanRedirectUrl } from './services/browser-helper'

let mainWindow: BrowserWindow | null = null

async function initDatabase(): Promise<void> {
  const targetDir = join(app.getPath('userData'), 'data')
  if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true })
  }
  const dbPath = join(targetDir, 'app.db')

  // Migration: If target db does not exist and has never been initialized/reset before, copy from legacy ban_win data if available
  const migratedMarker = join(targetDir, '.migrated')
  if (!fs.existsSync(dbPath) && !fs.existsSync(migratedMarker)) {
    const legacyPath = 'c:/Users/Trant/Documents/tools/scan_story/ban_win/data/app.db'
    if (fs.existsSync(legacyPath)) {
      try {
        fs.copyFileSync(legacyPath, dbPath)
        fs.writeFileSync(migratedMarker, new Date().toISOString())
        console.log('[App] Migrated legacy database from ban_win successfully!')
      } catch (err) {
        console.warn('[App] Failed to copy legacy database:', err)
      }
    }
  } else if (!fs.existsSync(migratedMarker)) {
    try {
      fs.writeFileSync(migratedMarker, new Date().toISOString())
    } catch {}
  }

  const db = getDatabaseService(dbPath)
  await db.initialize()
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 850,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    autoHideMenuBar: true,
    title: 'Ban Win 1 - Modern Automation Suite',
    icon,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      webviewTag: true, // Enable <webview> for Gemini AI embedding with full Google login support!
      contextIsolation: true,
      webSecurity: false // Allow seamless local video file playback and local media streaming
    }
  })


  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  registerIpcHandlers(mainWindow)

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.banwin1.app')

  // Start internal HTTP Range streaming media server
  try {
    await MediaServer.start()
  } catch (err) {
    console.warn('[App] Failed to start MediaServer:', err)
  }

  // Register protocol handler to stream local video files with full Range support
  protocol.handle('media-file', async (request) => {
    try {
      const filePath = resolveMediaProtocolPath(request.url)
      if (!filePath || !fs.existsSync(filePath)) {
        console.warn(`[media-file] File not found or path invalid: ${filePath}`)
        return new Response('File not found', { status: 404 })
      }

      // If MediaServer is active, forward with Range headers to support end-of-file moov atoms
      if (MediaServer.getPort() > 0) {
        const streamUrl = MediaServer.getStreamUrl(filePath)
        return await net.fetch(streamUrl, {
          method: request.method,
          headers: request.headers
        })
      }

      return await net.fetch(pathToFileURL(filePath).toString())
    } catch (err: any) {
      console.error(`[media-file] Error serving media stream:`, err)
      return new Response(`Error: ${err.message}`, { status: 500 })
    }
  })

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // Handle all <webview> link clicks (target="_blank", window.open) and redirect shims
  app.on('web-contents-created', (_, contents) => {
    if (contents.getType() === 'webview') {
      contents.setWindowOpenHandler((details) => {
        const currentUrl = contents.getURL()
        const targetUrl = cleanRedirectUrl(details.url)

        // For Gemini page embedded webview:
        if (currentUrl.includes('gemini.google.com')) {
          if (targetUrl.includes('accounts.google.com') || targetUrl.includes('myaccount.google.com')) {
            setImmediate(() => {
              if (!contents.isDestroyed()) contents.loadURL(targetUrl)
            })
            return { action: 'deny' }
          }
          shell.openExternal(targetUrl)
          return { action: 'deny' }
        }

        // For InAppBrowserModal (Facebook reels, news articles, external links):
        // Navigate the current webview to the clicked link
        setImmediate(() => {
          if (!contents.isDestroyed()) {
            contents.loadURL(targetUrl)
          }
        })
        return { action: 'deny' }
      })

      // Intercept will-navigate to bypass Facebook / Google redirect interstitials seamlessly
      contents.on('will-navigate', (event, url) => {
        const cleaned = cleanRedirectUrl(url)
        if (cleaned !== url) {
          event.preventDefault()
          setImmediate(() => {
            if (!contents.isDestroyed()) {
              contents.loadURL(cleaned)
            }
          })
        }
      })
    }
  })

  await initDatabase()
  createWindow()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  MediaServer.stop()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

