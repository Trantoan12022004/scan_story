import { FacebookDownloader } from './fb-downloader'
import { buildDefaultSampleVideoPath } from './video-checker'
import { getDatabaseService } from './database'
import fs from 'fs'

export interface QueueItem {
  stt: string
  url: string
  outputPath?: string
}

export class SampleDownloaderQueue {
  private static queue: QueueItem[] = []
  private static isRunning = false
  private static listeners: Array<(event: { stt: string; status: string; progress?: number }) => void> = []

  public static addListener(cb: (event: { stt: string; status: string; progress?: number }) => void) {
    this.listeners.push(cb)
  }

  public static removeListener(cb: (event: { stt: string; status: string; progress?: number }) => void) {
    this.listeners = this.listeners.filter((l) => l !== cb)
  }

  private static emit(event: { stt: string; status: string; progress?: number }) {
    for (const l of this.listeners) {
      try {
        l(event)
      } catch {}
    }
  }

  public static enqueue(item: QueueItem): void {
    if (!item.url || !item.stt) return
    this.queue.push(item)
    this.processNext()
  }

  public static enqueueBatch(items: QueueItem[]): void {
    for (const it of items) {
      if (it.url && it.stt) {
        this.queue.push(it)
      }
    }
    this.processNext()
  }

  private static async processNext(): Promise<void> {
    if (this.isRunning || this.queue.length === 0) return
    this.isRunning = true

    const current = this.queue.shift()!
    const targetPath = current.outputPath || buildDefaultSampleVideoPath(current.stt)

    // Check if already downloaded
    if (fs.existsSync(targetPath)) {
      this.emit({ stt: current.stt, status: 'exists', progress: 100 })
      this.isRunning = false
      this.processNext()
      return
    }

    this.emit({ stt: current.stt, status: 'downloading', progress: 0 })

    const res = await FacebookDownloader.downloadVideo(
      current.url,
      targetPath,
      (p) => {
        this.emit({ stt: current.stt, status: p.status, progress: p.percent })
      }
    )

    if (res.success) {
      // Update database row
      const db = getDatabaseService()
      db.updateSingleField(current.stt, 'video_mau', res.filePath)
      this.emit({ stt: current.stt, status: 'finished', progress: 100 })
    } else {
      this.emit({ stt: current.stt, status: 'error' })
    }

    this.isRunning = false
    this.processNext()
  }
}
