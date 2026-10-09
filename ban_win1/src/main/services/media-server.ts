import http from 'http'
import fs from 'fs'
import path from 'path'

export class MediaServer {
  private static server: http.Server | null = null
  private static port: number = 0

  public static async start(): Promise<number> {
    if (this.server && this.port > 0) {
      return this.port
    }

    return new Promise((resolve, reject) => {
      const server = http.createServer((req, res) => {
        // Enable CORS & Private Network Access for Electron renderer
        res.setHeader('Access-Control-Allow-Origin', '*')
        res.setHeader('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        res.setHeader('Access-Control-Allow-Headers', '*')
        res.setHeader('Access-Control-Allow-Private-Network', 'true')

        if (req.method === 'OPTIONS') {
          res.writeHead(204)
          res.end()
          return
        }


        try {
          const reqUrl = new URL(req.url || '/', `http://${req.headers.host || '127.0.0.1'}`)
          let filePath = reqUrl.searchParams.get('path')
          if (!filePath) {
            res.writeHead(400, { 'Content-Type': 'text/plain' })
            res.end('Missing path parameter')
            return
          }

          filePath = path.normalize(decodeURIComponent(filePath))
          if (!fs.existsSync(filePath)) {
            res.writeHead(404, { 'Content-Type': 'text/plain' })
            res.end('File not found')
            return
          }

          const stat = fs.statSync(filePath)
          const fileSize = stat.size

          // Determine Content-Type based on extension
          const ext = path.extname(filePath).toLowerCase()
          let contentType = 'video/mp4'
          if (ext === '.mkv') contentType = 'video/x-matroska'
          else if (ext === '.webm') contentType = 'video/webm'
          else if (ext === '.avi') contentType = 'video/x-msvideo'
          else if (ext === '.mov') contentType = 'video/quicktime'
          else if (ext === '.mp3') contentType = 'audio/mpeg'
          else if (ext === '.wav') contentType = 'audio/wav'

          const range = req.headers.range
          if (range) {
            // Parse Range: bytes=start-end
            const parts = range.replace(/bytes=/, '').split('-')
            const start = parseInt(parts[0], 10)
            const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1

            if (isNaN(start) || start >= fileSize || end >= fileSize || start > end) {
              res.writeHead(416, {
                'Content-Range': `bytes */${fileSize}`,
                'Content-Type': 'text/plain'
              })
              res.end('Requested range not satisfiable')
              return
            }

            const chunkSize = end - start + 1
            res.writeHead(206, {
              'Content-Range': `bytes ${start}-${end}/${fileSize}`,
              'Accept-Ranges': 'bytes',
              'Content-Length': chunkSize,
              'Content-Type': contentType
            })

            const stream = fs.createReadStream(filePath, { start, end })
            stream.pipe(res)
            req.on('close', () => {
              stream.destroy()
            })
          } else {
            res.writeHead(200, {
              'Content-Length': fileSize,
              'Content-Type': contentType,
              'Accept-Ranges': 'bytes'
            })
            const stream = fs.createReadStream(filePath)
            stream.pipe(res)
            req.on('close', () => {
              stream.destroy()
            })
          }
        } catch (err: any) {
          res.writeHead(500, { 'Content-Type': 'text/plain' })
          res.end(`Internal Error: ${err.message}`)
        }
      })

      server.listen(0, '127.0.0.1', () => {
        const address = server.address()
        if (address && typeof address === 'object') {
          this.port = address.port
          this.server = server
          console.log(`[MediaServer] Video streaming server started on http://127.0.0.1:${this.port}`)
          resolve(this.port)
        } else {
          reject(new Error('Failed to bind media server address'))
        }
      })

      server.on('error', (err) => {
        console.error('[MediaServer] Server error:', err)
        reject(err)
      })
    })
  }

  public static getPort(): number {
    return this.port
  }

  public static getStreamUrl(filePath: string): string {
    if (!filePath || this.port === 0) return ''
    return `http://127.0.0.1:${this.port}/video?path=${encodeURIComponent(filePath)}`
  }

  public static stop(): void {
    if (this.server) {
      this.server.close()
      this.server = null
      this.port = 0
    }
  }
}
