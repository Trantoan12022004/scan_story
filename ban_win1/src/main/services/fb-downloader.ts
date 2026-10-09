import { spawn } from 'child_process'
import path from 'path'
import fs from 'fs'
import { getBinaryPath } from './binary-resolver'

export interface VideoMetadata {
  title: string
  description: string
  duration: number
  uploader: string
  thumbnail: string
  formats?: any[]
}

export interface DownloadProgress {
  percent: number
  speed: string
  eta: string
  status: 'downloading' | 'finished' | 'error'
  filePath?: string
  error?: string
}

import axios from 'axios'

export class FacebookDownloader {
  public static async getMetadata(url: string): Promise<VideoMetadata | null> {
    const cleanUrl = (url || '').trim()
    if (!cleanUrl) return null

    const ytdlp = getBinaryPath('yt-dlp')

    const ytdlpPromise = new Promise<VideoMetadata | null>((resolve) => {
      const child = spawn(ytdlp, ['--dump-json', '--no-warnings', '--no-playlist', cleanUrl])

      let stdout = ''
      child.stdout.on('data', (data) => {
        stdout += data.toString()
      })

      child.on('close', (code) => {
        if (code === 0 && stdout) {
          try {
            const json = JSON.parse(stdout)
            const desc = (json.description || json.title || '').trim()
            resolve({
              title: json.title || desc || '',
              description: desc,
              duration: json.duration || 0,
              uploader: json.uploader || '',
              thumbnail: json.thumbnail || ''
            })
            return
          } catch { }
        }
        resolve(null)
      })

      child.on('error', () => {
        resolve(null)
      })
    })

    const meta = await Promise.race([
      ytdlpPromise,
      new Promise<null>((r) => setTimeout(() => r(null), 10000))
    ])

    if (meta && (meta.description || meta.title)) {
      return meta
    }

    // Direct HTTP scrape fallback for Facebook Reel caption / metadata
    try {
      const resp = await axios.get(cleanUrl, {
        headers: {
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        },
        timeout: 8000
      })
      const html = typeof resp.data === 'string' ? resp.data : ''
      if (html) {
        let desc = ''
        const mOg =
          html.match(/property=["']og:description["']\s+content=["']([^"']+)["']/i) ||
          html.match(/content=["']([^"']+)["']\s+property=["']og:description["']/i)
        if (mOg && mOg[1]) {
          desc = mOg[1].replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"').trim()
        } else {
          const mTitle = html.match(/<title>(.*?)<\/title>/i)
          if (mTitle && mTitle[1]) {
            desc = mTitle[1].replace(/\s*\|\s*Facebook/gi, '').replace(/\s*-\s*Facebook/gi, '').trim()
          }
        }
        if (desc) {
          return {
            title: desc,
            description: desc,
            duration: 0,
            uploader: '',
            thumbnail: ''
          }
        }
      }
    } catch { }

    return meta
  }

  public static downloadVideo(
    url: string,
    outputPath: string,
    onProgress?: (p: DownloadProgress) => void
  ): Promise<{ success: boolean; filePath: string; error?: string }> {
    const ytdlp = getBinaryPath('yt-dlp')
    const dir = path.dirname(outputPath)
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true })
    }

    return new Promise((resolve) => {
      const args = [
        '--newline',
        '--no-playlist',
        '-f',
        'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        '--merge-output-format',
        'mp4',
        '-o',
        outputPath,
        url
      ]

      const child = spawn(ytdlp, args)
      let lastErr = ''

      child.stdout.on('data', (chunk) => {
        const line = chunk.toString()
        // e.g. [download]  45.0% of 10.50MiB at 2.30MiB/s ETA 00:03
        const percentMatch = line.match(/(\d+(?:\.\d+)?)%/)
        const speedMatch = line.match(/at\s+([\d.]+\w+\/s)/)
        const etaMatch = line.match(/ETA\s+(\S+)/)

        if (percentMatch && onProgress) {
          onProgress({
            percent: parseFloat(percentMatch[1]),
            speed: speedMatch ? speedMatch[1] : '',
            eta: etaMatch ? etaMatch[1] : '',
            status: 'downloading'
          })
        }
      })

      child.stderr.on('data', (chunk) => {
        lastErr += chunk.toString()
      })

      child.on('close', (code) => {
        if (code === 0 && fs.existsSync(outputPath)) {
          if (onProgress) {
            onProgress({
              percent: 100,
              speed: '',
              eta: '',
              status: 'finished',
              filePath: outputPath
            })
          }
          resolve({ success: true, filePath: outputPath })
        } else {
          if (onProgress) {
            onProgress({
              percent: 0,
              speed: '',
              eta: '',
              status: 'error',
              error: lastErr || 'Download failed'
            })
          }
          resolve({ success: false, filePath: '', error: lastErr || 'Download failed' })
        }
      })

      child.on('error', (err) => {
        resolve({ success: false, filePath: '', error: err.message })
      })
    })
  }
}
