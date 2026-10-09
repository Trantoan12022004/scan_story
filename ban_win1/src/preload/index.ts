import { contextBridge, ipcRenderer } from 'electron'

const api = {
  db: {
    getVideos: (filter?: any) => ipcRenderer.invoke('db:get-videos', filter),
    getVideoByStt: (stt: string) => ipcRenderer.invoke('db:get-video-by-stt', stt),
    upsertVideo: (data: any) => ipcRenderer.invoke('db:upsert-video', data),
    deleteVideo: (stt: string) => ipcRenderer.invoke('db:delete-video', stt),
    updateSingleField: (stt: string, field: string, value: any) =>
      ipcRenderer.invoke('db:update-single-field', stt, field, value),
    bulkInsertReels: (urls: string[], deduplicate?: boolean) =>
      ipcRenderer.invoke('db:bulk-insert-reels', urls, deduplicate),
    getStatCounts: () => ipcRenderer.invoke('db:get-stat-counts'),
    getSettings: () => ipcRenderer.invoke('db:get-settings'),
    setSetting: (key: string, value: string) => ipcRenderer.invoke('db:set-setting', key, value),
    getPrompts: () => ipcRenderer.invoke('db:get-prompts'),
    savePrompt: (name: string, content: string, promptId?: number) =>
      ipcRenderer.invoke('db:save-prompt', name, content, promptId),
    deletePrompt: (promptId: number) => ipcRenderer.invoke('db:delete-prompt', promptId),
    getDownloadedVideos: (limit?: number) => ipcRenderer.invoke('db:get-downloaded-videos', limit),
    addDownloadedVideo: (data: any) => ipcRenderer.invoke('db:add-downloaded-video', data),
    deleteDownloadedVideo: (id: number) => ipcRenderer.invoke('db:delete-downloaded-video', id),
    getScrapedStories: (limit?: number) => ipcRenderer.invoke('db:get-scraped-stories', limit),
    addScrapedStory: (data: any) => ipcRenderer.invoke('db:add-scraped-story', data),
    syncStatuses: (items?: any[]) => ipcRenderer.invoke('db:sync-statuses', items),
    clearVideos: () => ipcRenderer.invoke('db:clear-videos'),
    clearDownloadedVideos: () => ipcRenderer.invoke('db:clear-downloaded-videos'),
    clearScrapedStories: () => ipcRenderer.invoke('db:clear-scraped-stories'),
    clearPrompts: () => ipcRenderer.invoke('db:clear-prompts'),
    resetDatabase: (options?: { keepSettings?: boolean }) =>
      ipcRenderer.invoke('db:reset-database', options),
    getDatabaseStats: () => ipcRenderer.invoke('db:get-stats'),
    updatePostStats: (stt: string, stats: any) =>
      ipcRenderer.invoke('db:update-post-stats', stt, stats)
  },
  video: {
    checkBatch: (items: any[], autoSync = true) => ipcRenderer.invoke('video:check-batch', items, autoSync),
    checkSampleBatch: (items: any[]) => ipcRenderer.invoke('video:check-sample-batch', items),
    checkSingle: (pathStr: string, stt?: string) => ipcRenderer.invoke('video:check-single', pathStr, stt),
    getStreamUrl: (pathStr: string) => ipcRenderer.invoke('video:get-stream-url', pathStr)
  },

  fb: {
    getMetadata: (url: string) => ipcRenderer.invoke('fb:get-metadata', url),
    download: (url: string, outputPath: string) => ipcRenderer.invoke('fb:download', url, outputPath),
    onProgress: (cb: (progress: any) => void) => {
      const listener = (_: any, p: any) => cb(p)
      ipcRenderer.on('download:progress', listener)
      return () => {
        ipcRenderer.removeListener('download:progress', listener)
      }
    }
  },
  sampleQueue: {
    enqueue: (item: any) => ipcRenderer.invoke('sample:enqueue', item),
    enqueueBatch: (items: any[]) => ipcRenderer.invoke('sample:enqueue-batch', items),
    onEvent: (cb: (event: any) => void) => {
      const listener = (_: any, ev: any) => cb(ev)
      ipcRenderer.on('sample-queue:event', listener)
      return () => {
        ipcRenderer.removeListener('sample-queue:event', listener)
      }
    }
  },
  ai: {
    extractCaption: (url: string) => ipcRenderer.invoke('ai:extract-caption', url),
    mergeContent: (caption: string, baoMoiUrl: string) =>
      ipcRenderer.invoke('ai:merge-content', caption, baoMoiUrl),
    createContent: (params: {
      baiGoc?: string
      baoMoi?: string
      currentContent?: string
      forceReExtract?: boolean
    }) => ipcRenderer.invoke('ai:create-content', params),
    extractBaoGoc: (url: string) => ipcRenderer.invoke('ai:extract-bao-goc', url),
    batchMergeContent: () => ipcRenderer.invoke('ai:batch-merge-content'),
    autoMergeAll: () => ipcRenderer.invoke('ai:auto-merge-all'),
    generateContent: (prompt: string, content: string) =>
      ipcRenderer.invoke('ai:generate-content', prompt, content)
  },

  story: {
    startScrape: (options: any) => ipcRenderer.invoke('story:start-scrape', options),
    cancelScrape: () => ipcRenderer.invoke('story:cancel-scrape'),
    testCms: (cmsUrl: string, cmsUser: string, cmsPass: string) =>
      ipcRenderer.invoke('story:test-cms', cmsUrl, cmsUser, cmsPass),
    translateText: (text: string, targetLang?: string) =>
      ipcRenderer.invoke('story:translate-text', text, targetLang),
    translateChapter: (chapter: any, targetLang?: string) =>
      ipcRenderer.invoke('story:translate-chapter', chapter, targetLang),
    publish: (storyInfo: any, chapters: any[]) =>
      ipcRenderer.invoke('story:publish', storyInfo, chapters),
    onLog: (cb: (msg: string) => void) => {
      const listener = (_: any, m: any) => cb(m)
      ipcRenderer.on('story:log', listener)
      ipcRenderer.on('publish:log', listener)
      return () => {
        ipcRenderer.removeListener('story:log', listener)
        ipcRenderer.removeListener('publish:log', listener)
      }
    },
    onProgress: (cb: (data: { percent: number; status: string }) => void) => {
      const listener = (_: any, p: any) => cb(p)
      ipcRenderer.on('story:progress', listener)
      return () => {
        ipcRenderer.removeListener('story:progress', listener)
      }
    }
  },
  license: {
    verify: (sheetUrl?: string) => ipcRenderer.invoke('license:verify', sheetUrl),
    getHwid: () => ipcRenderer.invoke('license:get-hwid')
  },
  dialog: {
    openFolder: () => ipcRenderer.invoke('dialog:open-folder'),
    openFile: (filters?: any) => ipcRenderer.invoke('dialog:open-file', filters)
  },
  shell: {
    openPath: (filePath: string) => ipcRenderer.invoke('shell:open-path', filePath),
    playFile: (filePath: string) => ipcRenderer.invoke('shell:play-file', filePath),
    openExternal: (url: string) => ipcRenderer.invoke('shell:open-external', url)
  },
  stats: {
    scanPost: (url: string) => ipcRenderer.invoke('stats:scan-post', url),
    scanAndUpdate: (stt: string, url: string) =>
      ipcRenderer.invoke('stats:scan-and-update', stt, url),
    scanBatch: (items: Array<{ stt: string; url: string }>) =>
      ipcRenderer.invoke('stats:scan-batch', items),
    onBatchProgress: (cb: (data: { current: number; total: number; stt: string }) => void) => {
      const listener = (_: any, data: any) => cb(data)
      ipcRenderer.on('stats:batch-progress', listener)
      return () => {
        ipcRenderer.removeListener('stats:batch-progress', listener)
      }
    }
  }
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  ; (window as any).api = api
}

export type IpcApi = typeof api

