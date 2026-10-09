import { ipcMain, dialog, shell, BrowserWindow } from 'electron'
import fs from 'fs'
import { getDatabaseService } from './services/database'
import { checkVideoFilesBatch, checkSampleVideosBatch, checkVideoFile } from './services/video-checker'
import { FacebookDownloader } from './services/fb-downloader'
import { SampleDownloaderQueue } from './services/sample-downloader'
import { ContentGenerator } from './services/content-generator'
import { TranslatorService, ChapterContent } from './services/translator'
import { CMSPublisher, StoryInfo } from './services/publisher'
import { StoryScraperEngine } from './services/story-scraper'
import { LicenseManager } from './services/license-manager'
import { ConfigService } from './services/config'
import { MediaServer } from './services/media-server'
import { PostStatsScanner } from './services/post-stats-scanner'


export function registerIpcHandlers(mainWindow: BrowserWindow): void {
  const db = getDatabaseService()

  // 1. DATABASE - VIDEOS
  ipcMain.handle('db:get-videos', async (_, filter) => {
    return db.getAllVideos(filter)
  })

  ipcMain.handle('db:get-video-by-stt', async (_, stt: string) => {
    return db.getVideoByStt(stt)
  })

  ipcMain.handle('db:upsert-video', async (_, data: Record<string, any>) => {
    return db.upsertVideo(data)
  })

  ipcMain.handle('db:delete-video', async (_, stt: string) => {
    return db.deleteVideo(stt)
  })

  ipcMain.handle('db:update-single-field', async (_, stt: string, field: string, value: any) => {
    return db.updateSingleField(stt, field, value)
  })

  ipcMain.handle('db:bulk-insert-reels', async (_, urls: string[], deduplicate = true) => {
    return db.bulkInsertReels(urls, deduplicate)
  })

  ipcMain.handle('db:get-stat-counts', async () => {
    return db.getStatCounts()
  })

  ipcMain.handle('db:update-post-stats', async (_, stt: string, stats: any) => {
    return db.updatePostStats(stt, stats)
  })

  // 2. DATABASE - SETTINGS
  ipcMain.handle('db:get-settings', async () => {
    const settings = db.getAllSettings()
    ConfigService.setAll(settings)
    return settings
  })

  ipcMain.handle('db:set-setting', async (_, key: string, value: string) => {
    db.setSetting(key, value)
    ConfigService.set(key, value)
    return true
  })

  // 3. DATABASE - PROMPTS
  ipcMain.handle('db:get-prompts', async () => {
    return db.getAllPrompts()
  })

  ipcMain.handle('db:save-prompt', async (_, name: string, content: string, promptId?: number) => {
    return db.savePrompt(name, content, promptId)
  })

  ipcMain.handle('db:delete-prompt', async (_, promptId: number) => {
    db.deletePrompt(promptId)
    return true
  })

  // 4. DATABASE - DOWNLOADED & SCRAPED
  ipcMain.handle('db:get-downloaded-videos', async (_, limit = 50) => {
    return db.getDownloadedVideos(limit)
  })

  ipcMain.handle('db:add-downloaded-video', async (_, data: Record<string, any>) => {
    return db.addDownloadedVideo(data)
  })

  ipcMain.handle('db:delete-downloaded-video', async (_, id: number) => {
    db.deleteDownloadedVideo(id)
    return true
  })

  ipcMain.handle('db:get-scraped-stories', async (_, limit = 50) => {
    return db.getScrapedStories(limit)
  })

  ipcMain.handle('db:add-scraped-story', async (_, data: Record<string, any>) => {
    return db.addScrapedStory(data)
  })

  // 4b. DATABASE - RESET & CLEAR UTILITIES
  ipcMain.handle('db:clear-videos', async () => {
    return db.clearAllVideos()
  })

  ipcMain.handle('db:clear-downloaded-videos', async () => {
    return db.clearDownloadedVideos()
  })

  ipcMain.handle('db:clear-scraped-stories', async () => {
    return db.clearScrapedStories()
  })

  ipcMain.handle('db:clear-prompts', async () => {
    return db.clearPrompts()
  })

  ipcMain.handle('db:reset-database', async (_, options?: { keepSettings?: boolean }) => {
    return db.resetDatabase(options)
  })

  ipcMain.handle('db:get-stats', async () => {
    return db.getDatabaseStats()
  })

  // 5. VIDEO CHECKER (BATCH & SINGLE)
  ipcMain.handle('video:check-batch', async (_, items: Array<Record<string, any>>, autoSync = true) => {
    const results = checkVideoFilesBatch(items)
    if (autoSync && Array.isArray(items) && items.length > 0) {
      db.syncStatusesWithCheck(items, results)
    }
    return results
  })

  ipcMain.handle('db:sync-statuses', async (_, items?: Array<Record<string, any>>) => {
    const list = items || db.getAllVideos()
    const results = checkVideoFilesBatch(list)
    return db.syncStatusesWithCheck(list, results)
  })

  ipcMain.handle('video:check-sample-batch', async (_, items: Array<Record<string, any>>) => {
    return checkSampleVideosBatch(items)
  })

  ipcMain.handle('video:check-single', async (_, pathStr: string, stt?: string) => {
    return checkVideoFile(pathStr, stt)
  })

  ipcMain.handle('video:get-stream-url', async (_, pathStr: string) => {
    return MediaServer.getStreamUrl(pathStr)
  })


  // 6. DOWNLOADERS
  ipcMain.handle('fb:get-metadata', async (_, url: string) => {
    return FacebookDownloader.getMetadata(url)
  })

  ipcMain.handle('fb:download', async (_, url: string, outputPath: string) => {
    return FacebookDownloader.downloadVideo(url, outputPath, (p) => {
      mainWindow.webContents.send('download:progress', p)
    })
  })

  ipcMain.handle('sample:enqueue', async (_, item) => {
    SampleDownloaderQueue.enqueue(item)
    return true
  })

  ipcMain.handle('sample:enqueue-batch', async (_, items) => {
    SampleDownloaderQueue.enqueueBatch(items)
    return true
  })

  // Forward queue events to renderer
  SampleDownloaderQueue.addListener((event) => {
    if (!mainWindow.isDestroyed()) {
      mainWindow.webContents.send('sample-queue:event', event)
    }
  })

  // 7. CONTENT GENERATION (FB CAPTION, MERGE, BAO GOC & DEEPSEEK)
  ipcMain.handle('ai:extract-caption', async (_, url: string) => {
    return ContentGenerator.extractReelCaption(url)
  })

  ipcMain.handle('ai:merge-content', async (_, caption: string, baoMoiUrl: string) => {
    return ContentGenerator.mergeContent(caption, baoMoiUrl)
  })

  ipcMain.handle(
    'ai:create-content',
    async (
      _,
      params: {
        baiGoc?: string
        baoMoi?: string
        currentContent?: string
        forceReExtract?: boolean
      }
    ) => {
      return ContentGenerator.createContentForReel(
        params?.baiGoc,
        params?.baoMoi,
        params?.currentContent,
        params?.forceReExtract
      )
    }
  )

  ipcMain.handle('ai:extract-bao-goc', async (_, url: string) => {
    return ContentGenerator.extractBaoGoc(url)
  })

  ipcMain.handle('ai:batch-merge-content', async () => {
    return ContentGenerator.batchMergeContent(db)
  })

  ipcMain.handle('ai:auto-merge-all', async () => {
    return ContentGenerator.autoMergeAllEligible(db)
  })


  ipcMain.handle('ai:generate-content', async (_, prompt: string, content: string) => {
    const apiKey = db.getSetting('deepseek_api_key', '')
    return ContentGenerator.generateWithDeepSeek(apiKey, prompt, content)
  })

  // 8. TRANSLATOR & SCRAPER
  let activeScraperEngine: { cancel: () => void } | null = null

  ipcMain.handle('story:start-scrape', async (_, options: Record<string, any>) => {
    let isCancelled = false
    const engine = new StoryScraperEngine({
      onLog: (msg) => {
        if (!mainWindow.isDestroyed()) {
          mainWindow.webContents.send('story:log', msg)
        }
      },
      onProgress: (pct, status) => {
        if (!mainWindow.isDestroyed()) {
          mainWindow.webContents.send('story:progress', { percent: pct, status })
        }
      },
      isCancelled: () => isCancelled
    })

    activeScraperEngine = {
      cancel: () => {
        isCancelled = true
      }
    }

    try {
      const res = await engine.run(options as any)
      return res
    } finally {
      activeScraperEngine = null
    }
  })

  ipcMain.handle('story:cancel-scrape', async () => {
    if (activeScraperEngine) {
      activeScraperEngine.cancel()
      return true
    }
    return false
  })

  ipcMain.handle('story:test-cms', async (_, cmsUrl: string, cmsUser: string, cmsPass: string) => {
    const publisher = new CMSPublisher(cmsUrl, cmsUser, cmsPass)
    const ok = await publisher.login()
    return {
      ok,
      error: publisher.lastError,
      cmsType: publisher.cmsType,
      categories: publisher.availableCategories
    }
  })


  ipcMain.handle('story:translate-text', async (_, text: string, targetLang = 'en') => {
    const translator = new TranslatorService(targetLang)
    return translator.translateText(text)
  })

  ipcMain.handle('story:translate-chapter', async (_, chapter: ChapterContent, targetLang = 'en') => {
    const translator = new TranslatorService(targetLang)
    return translator.translateChapter(chapter)
  })

  // 9. PUBLISHER
  ipcMain.handle('story:publish', async (_, storyInfo: StoryInfo, chapters: ChapterContent[]) => {
    const cmsUrl = db.getSetting('cms_url', 'https://vmnewstoryus.cfx.bz')
    const cmsUser = db.getSetting('cms_user', 'admin')
    const cmsPass = db.getSetting('cms_pass', '')

    const publisher = new CMSPublisher(cmsUrl, cmsUser, cmsPass)
    return publisher.publishStory(storyInfo, chapters, (msg) => {
      mainWindow.webContents.send('publish:log', msg)
    })
  })

  // 10. LICENSE
  ipcMain.handle('license:verify', async (_, sheetUrl?: string) => {
    return LicenseManager.verifyLicense(sheetUrl)
  })

  ipcMain.handle('license:get-hwid', async () => {
    return LicenseManager.verifyLicense().then((s) => s.hwid)
  })

  // 11. SYSTEM DIALOGS & SHELL
  ipcMain.handle('dialog:open-folder', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory']
    })
    return result.canceled ? null : result.filePaths[0]
  })

  ipcMain.handle('dialog:open-file', async (_, filters) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile'],
      filters: filters || [{ name: 'Videos', extensions: ['mp4', 'mkv', 'avi', 'mov'] }]
    })
    return result.canceled ? null : result.filePaths[0]
  })

  ipcMain.handle('shell:open-path', async (_, filePath: string) => {
    if (fs.existsSync(filePath)) {
      shell.showItemInFolder(filePath)
      return true
    }
    return false
  })

  ipcMain.handle('shell:play-file', async (_, filePath: string) => {
    if (fs.existsSync(filePath)) {
      await shell.openPath(filePath)
      return true
    }
    return false
  })

  ipcMain.handle('shell:open-external', async (_, url: string) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      shell.openExternal(url)
      return true
    }
    return false
  })

  // 12. POST STATISTICS SCANNER
  ipcMain.handle('stats:scan-post', async (_, url: string) => {
    return PostStatsScanner.scanPostStats(url)
  })

  ipcMain.handle('stats:scan-and-update', async (_, stt: string, url: string) => {
    const stats = await PostStatsScanner.scanPostStats(url)
    db.updatePostStats(stt, stats)
    return stats
  })

  ipcMain.handle('stats:scan-batch', async (event, items: Array<{ stt: string; url: string }>) => {
    const results: Record<string, any> = {}
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (!item.url) continue
      event.sender.send('stats:batch-progress', {
        current: i + 1,
        total: items.length,
        stt: item.stt
      })
      try {
        const stats = await PostStatsScanner.scanPostStats(item.url)
        db.updatePostStats(item.stt, stats)
        results[item.stt] = stats
      } catch (e) {
        console.warn(`[stats:scan-batch] Error scanning stt #${item.stt}:`, e)
      }
    }
    return results
  })
}



