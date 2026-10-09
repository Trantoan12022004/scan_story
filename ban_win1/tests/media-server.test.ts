import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { MediaServer } from '../src/main/services/media-server'
import http from 'http'
import fs from 'fs'
import path from 'path'

describe('MediaServer Service', () => {
  let port = 0
  const testFile = path.resolve(__dirname, 'temp_test_video.mp4')

  beforeAll(async () => {
    // Create a 1MB dummy file for range testing
    const buf = Buffer.alloc(1024 * 1024, 0x41) // 1MB of 'A'
    fs.writeFileSync(testFile, buf)
    port = await MediaServer.start()
  })

  afterAll(() => {
    MediaServer.stop()
    if (fs.existsSync(testFile)) {
      fs.unlinkSync(testFile)
    }
  })

  // 1. HAPPY PATHS
  describe('Happy Paths', () => {
    it('starts media server and assigns a valid listening port', () => {
      expect(port).toBeGreaterThan(0)
      expect(MediaServer.getPort()).toBe(port)
    })

    it('generates stream URL with localhost and path param', () => {
      const url = MediaServer.getStreamUrl(testFile)
      expect(url).toContain(`http://127.0.0.1:${port}/video?path=`)
      expect(url).toContain(encodeURIComponent(testFile))
    })

    it('responds with 200 and Accept-Ranges when no Range header is sent', async () => {
      const streamUrl = MediaServer.getStreamUrl(testFile)
      const u = new URL(streamUrl)

      const res = await new Promise<{ statusCode?: number; headers: http.IncomingHttpHeaders }>((resolve) => {
        http.get({ host: u.hostname, port: u.port, path: u.pathname + u.search }, (response) => {
          resolve({ statusCode: response.statusCode, headers: response.headers })
        })
      })

      expect(res.statusCode).toBe(200)
      expect(res.headers['accept-ranges']).toBe('bytes')
      expect(res.headers['content-type']).toBe('video/mp4')
      expect(res.headers['content-length']).toBe(String(1024 * 1024))
    })

    it('responds with 206 Partial Content when Range header is sent (e.g. for moov atom at file end)', async () => {
      const streamUrl = MediaServer.getStreamUrl(testFile)
      const u = new URL(streamUrl)

      const start = 1024 * 1024 - 1000
      const end = 1024 * 1024 - 1

      const res = await new Promise<{ statusCode?: number; headers: http.IncomingHttpHeaders; data: Buffer }>((resolve) => {
        const req = http.request(
          {
            host: u.hostname,
            port: u.port,
            path: u.pathname + u.search,
            headers: { Range: `bytes=${start}-${end}` }
          },
          (response) => {
            const chunks: Buffer[] = []
            response.on('data', (c) => chunks.push(c))
            response.on('end', () => {
              resolve({
                statusCode: response.statusCode,
                headers: response.headers,
                data: Buffer.concat(chunks)
              })
            })
          }
        )
        req.end()
      })

      expect(res.statusCode).toBe(206)
      expect(res.headers['content-range']).toBe(`bytes ${start}-${end}/${1024 * 1024}`)
      expect(res.headers['content-length']).toBe('1000')
      expect(res.data.length).toBe(1000)
    })
  })

  // 2. EDGE CASES
  describe('Edge Cases', () => {
    it('returns empty string when getting stream URL for empty path', () => {
      expect(MediaServer.getStreamUrl('')).toBe('')
    })

    it('returns 404 when file does not exist on disk', async () => {
      const missingUrl = MediaServer.getStreamUrl('C:\\non_existent_video_file.mp4')
      const u = new URL(missingUrl)

      const res = await new Promise<number>((resolve) => {
        http.get({ host: u.hostname, port: u.port, path: u.pathname + u.search }, (response) => {
          resolve(response.statusCode || 0)
        })
      })

      expect(res).toBe(404)
    })

    it('handles OPTIONS preflight requests for CORS', async () => {
      const streamUrl = MediaServer.getStreamUrl(testFile)
      const u = new URL(streamUrl)

      const res = await new Promise<{ statusCode?: number; headers: http.IncomingHttpHeaders }>((resolve) => {
        const req = http.request(
          {
            method: 'OPTIONS',
            host: u.hostname,
            port: u.port,
            path: u.pathname + u.search
          },
          (response) => {
            resolve({ statusCode: response.statusCode, headers: response.headers })
          }
        )
        req.end()
      })

      expect(res.statusCode).toBe(204)
      expect(res.headers['access-control-allow-origin']).toBe('*')
    })
  })

  // 3. ERROR HANDLING
  describe('Error Handling', () => {
    it('returns 416 when requested Range is out of bounds', async () => {
      const streamUrl = MediaServer.getStreamUrl(testFile)
      const u = new URL(streamUrl)

      const res = await new Promise<number>((resolve) => {
        const req = http.request(
          {
            host: u.hostname,
            port: u.port,
            path: u.pathname + u.search,
            headers: { Range: `bytes=99999999-999999999` }
          },
          (response) => {
            resolve(response.statusCode || 0)
          }
        )
        req.end()
      })

      expect(res).toBe(416)
    })

    it('returns 400 when path parameter is missing', async () => {
      const res = await new Promise<number>((resolve) => {
        http.get({ host: '127.0.0.1', port, path: '/video' }, (response) => {
          resolve(response.statusCode || 0)
        })
      })

      expect(res).toBe(400)
    })
  })
})
