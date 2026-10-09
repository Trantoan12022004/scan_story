import { describe, it, expect, vi, beforeEach } from 'vitest'

const handlers = new Map<string, Function>()

vi.mock('electron', () => {
  return {
    ipcMain: {
      handle: vi.fn((channel: string, handler: Function) => {
        handlers.set(channel, handler)
      }),
      on: vi.fn()
    },
    dialog: {
      showOpenDialog: vi.fn()
    },
    shell: {
      showItemInFolder: vi.fn(),
      openPath: vi.fn(),
      openExternal: vi.fn((url: string) => url)
    },
    BrowserWindow: vi.fn()
  }
})

vi.mock('../src/main/services/database', () => {
  return {
    getDatabaseService: vi.fn(() => ({
      updatePostStats: vi.fn(),
      getAllVideos: vi.fn(),
      getVideoByStt: vi.fn(),
      upsertVideo: vi.fn(),
      deleteVideo: vi.fn(),
      updateSingleField: vi.fn(),
      bulkInsertReels: vi.fn(),
      getStatCounts: vi.fn(),
      getAllSettings: vi.fn(() => ({})),
      setSetting: vi.fn()
    }))
  }
})

vi.mock('../src/main/services/post-stats-scanner', () => {
  return {
    PostStatsScanner: {
      scanPostStats: vi.fn().mockImplementation(async (url: string) => {
        if (url.includes('error-fail')) {
          throw new Error('Network timeout during scan')
        }
        return { views: 5000, likes: 250, comments: 45, scanned_at: '2026-10-09T07:00:00.000Z' }
      })
    }
  }
})

describe('IPC Handlers Registration & Execution Test Suite', () => {
  beforeEach(async () => {
    handlers.clear()
    // Dynamic import to ensure mocks are active
    const { registerIpcHandlers } = await import('../src/main/ipc')
    registerIpcHandlers({} as any)
  })

  // 1. HAPPY PATH: All handlers registered properly and process expected data
  describe('Happy Paths', () => {
    it('registers essential IPC handler channels', () => {
      const expectedChannels = [
        'db:get-videos',
        'db:upsert-video',
        'db:update-post-stats',
        'stats:scan-post',
        'stats:scan-and-update',
        'stats:scan-batch',
        'shell:open-external'
      ]

      for (const ch of expectedChannels) {
        expect(handlers.has(ch), `Missing IPC channel: ${ch}`).toBe(true)
      }
    })

    it('stats:scan-batch processes valid items and dispatches progress events', async () => {
      const scanBatchHandler = handlers.get('stats:scan-batch')
      expect(scanBatchHandler).toBeDefined()

      const sentEvents: any[] = []
      const mockEvent = {
        sender: {
          send: vi.fn((channel: string, payload: any) => {
            sentEvents.push({ channel, payload })
          })
        }
      }

      const items = [
        { stt: '1', url: 'https://www.facebook.com/reel/11111' },
        { stt: '2', url: 'https://www.facebook.com/reel/22222' }
      ]

      const results = await scanBatchHandler!(mockEvent, items)

      expect(results).toBeDefined()
      expect(results['1']).toEqual(
        expect.objectContaining({ views: 5000, likes: 250, comments: 45 })
      )
      expect(results['2']).toEqual(
        expect.objectContaining({ views: 5000, likes: 250, comments: 45 })
      )
      expect(mockEvent.sender.send).toHaveBeenCalledTimes(2)
      expect(sentEvents[0].payload).toEqual({ current: 1, total: 2, stt: '1' })
      expect(sentEvents[1].payload).toEqual({ current: 2, total: 2, stt: '2' })
    })

    it('shell:open-external opens valid http/https URLs', async () => {
      const openExternalHandler = handlers.get('shell:open-external')
      expect(openExternalHandler).toBeDefined()

      const result = await openExternalHandler!({}, 'https://facebook.com')
      expect(result).toBe(true)
    })
  })

  // 2. EDGE CASES: Empty lists, missing URLs, invalid protocols
  describe('Edge Cases', () => {
    it('stats:scan-batch returns empty object when given empty array', async () => {
      const scanBatchHandler = handlers.get('stats:scan-batch')
      const mockEvent = { sender: { send: vi.fn() } }

      const results = await scanBatchHandler!(mockEvent, [])
      expect(results).toEqual({})
      expect(mockEvent.sender.send).not.toHaveBeenCalled()
    })

    it('stats:scan-batch skips items with missing or empty url', async () => {
      const scanBatchHandler = handlers.get('stats:scan-batch')
      const mockEvent = { sender: { send: vi.fn() } }

      const items = [
        { stt: '1', url: '' },
        { stt: '2', url: 'https://www.facebook.com/reel/valid' }
      ]

      const results = await scanBatchHandler!(mockEvent, items)
      expect(results['1']).toBeUndefined()
      expect(results['2']).toBeDefined()
      expect(mockEvent.sender.send).toHaveBeenCalledTimes(1)
    })

    it('shell:open-external rejects non-http/https schemes for safety', async () => {
      const openExternalHandler = handlers.get('shell:open-external')
      const result = await openExternalHandler!({}, 'file:///etc/passwd')
      expect(result).toBe(false)
    })
  })

  // 3. ERROR HANDLING: Survives item scan failures and continues loop
  describe('Error Handling', () => {
    it('stats:scan-batch gracefully recovers when a single item throws an error', async () => {
      const scanBatchHandler = handlers.get('stats:scan-batch')
      const mockEvent = { sender: { send: vi.fn() } }

      const items = [
        { stt: '1', url: 'https://error-fail.com' },
        { stt: '2', url: 'https://www.facebook.com/reel/success' }
      ]

      // Should not throw
      const results = await scanBatchHandler!(mockEvent, items)
      expect(results['1']).toBeUndefined()
      expect(results['2']).toBeDefined()
      expect(results['2'].views).toBe(5000)
    })
  })
})
