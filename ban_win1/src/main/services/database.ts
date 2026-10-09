import initSqlJs, { Database, SqlJsStatic } from 'sql.js'
import fs from 'fs'
import path from 'path'
import {
  determineVideoStatus,
  isPostUrl,
  hasContentText,
  STATUS_POSTED,
  STATUS_CONTENT_DONE,
  STATUS_VIDEO_READY,
  STATUS_FAILED
} from './status-engine'
import { buildDefaultSampleVideoPath, VideoCheckResult } from './video-checker'

export interface VideoRow {
  id?: number
  stt: string
  status?: string
  trang_thai_video?: string
  bai_goc?: string
  video_mau?: string
  prompt_video?: string
  frame_dau_tien?: string
  bao_goc?: string
  bao_moi?: string
  trang_thai_dang_bai?: string
  content?: string
  link_video?: string
  bai_viet_da_dang?: string
  views_count?: number
  likes_count?: number
  comments_count?: number
  stats_updated_at?: string
  created_at?: string
  updated_at?: string
  synced_at?: string
  local_modified?: number
  local_modified_time?: number
}

export interface PromptItem {
  id?: number
  name: string
  content: string
  created_at?: string
}

export interface DownloadedVideoItem {
  id?: number
  url: string
  title?: string
  author?: string
  duration?: string
  quality?: string
  file_path?: string
  file_size?: string
  thumbnail_url?: string
  downloaded_at?: string
}

export interface ScrapedStoryItem {
  id?: number
  url: string
  title?: string
  slug?: string
  chapters_count?: number
  output_dir?: string
  translated?: number
  published?: number
  cms_url?: string
  scraped_at?: string
}

export interface StatCounts {
  total: number
  fetch_video: number
  video_ready: number
  content_done: number
  posted: number
  failed: number
  video_done?: number
  has_file?: number
  post_done?: number
}

let SQL: SqlJsStatic | null = null

export class DatabaseService {
  private db: Database | null = null
  private dbPath: string
  private settingsCache: Record<string, string> = {}
  private initialized = false

  constructor(dbPath?: string) {
    if (dbPath) {
      this.dbPath = dbPath
    } else {
      const defaultDir = path.join(process.cwd(), 'data')
      this.dbPath = path.join(defaultDir, 'app.db')
    }
  }

  public async initialize(): Promise<void> {
    if (this.initialized) return

    if (!SQL) {
      SQL = await initSqlJs({
        locateFile: (file) => {
          const adjacent = path.join(__dirname, file)
          if (fs.existsSync(adjacent)) return adjacent
          const nm = path.join(process.cwd(), 'node_modules', 'sql.js', 'dist', file)
          if (fs.existsSync(nm)) return nm
          return file
        }
      })
    }

    if (fs.existsSync(this.dbPath)) {
      try {
        const buffer = fs.readFileSync(this.dbPath)
        this.db = new SQL.Database(buffer)
      } catch (err) {
        console.warn(`[DatabaseService] Failed to load DB file, creating new: ${err}`)
        this.db = new SQL.Database()
      }
    } else {
      this.db = new SQL.Database()
    }

    this.initSchema()
    this.initialized = true
  }

  private saveToDisk(): void {
    if (!this.db || !this.dbPath) return
    try {
      const data = this.db.export()
      const dir = path.dirname(this.dbPath)
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true })
      }
      fs.writeFileSync(this.dbPath, Buffer.from(data))
    } catch (err) {
      console.error(`[DatabaseService] Error saving to disk: ${err}`)
    }
  }

  private initSchema(): void {
    if (!this.db) return

    this.db.run(`
      CREATE TABLE IF NOT EXISTS videos (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        stt                 TEXT    NOT NULL UNIQUE,
        status              TEXT    DEFAULT 'FETCH VIDEO',
        trang_thai_video     TEXT    DEFAULT '',
        bai_goc             TEXT    DEFAULT '',
        video_mau           TEXT    DEFAULT '',
        prompt_video        TEXT    DEFAULT '',
        frame_dau_tien      TEXT    DEFAULT '',
        bao_goc             TEXT    DEFAULT '',
        bao_moi             TEXT    DEFAULT '',
        trang_thai_dang_bai TEXT    DEFAULT 'chưa hoàn thành',
        content             TEXT    DEFAULT '',
        link_video          TEXT    DEFAULT '',
        bai_viet_da_dang    TEXT    DEFAULT '',
        views_count         INTEGER DEFAULT 0,
        likes_count         INTEGER DEFAULT 0,
        comments_count      INTEGER DEFAULT 0,
        stats_updated_at    DATETIME,
        created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
        synced_at           DATETIME,
        local_modified      INTEGER DEFAULT 0,
        local_modified_time REAL    DEFAULT 0.0
      );
    `)

    this.db.run(`CREATE INDEX IF NOT EXISTS idx_videos_stt ON videos(stt);`)
    this.db.run(`CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);`)

    // Check table info for migrations
    const res = this.db.exec("PRAGMA table_info('videos');")
    if (res.length > 0) {
      const columns = res[0].values.map((col) => String(col[1]))
      if (!columns.includes('status')) {
        this.db.run("ALTER TABLE videos ADD COLUMN status TEXT DEFAULT 'FETCH VIDEO';")
      }
      if (!columns.includes('video_mau')) {
        this.db.run("ALTER TABLE videos ADD COLUMN video_mau TEXT DEFAULT '';")
      }
      if (!columns.includes('views_count')) {
        this.db.run('ALTER TABLE videos ADD COLUMN views_count INTEGER DEFAULT 0;')
      }
      if (!columns.includes('likes_count')) {
        this.db.run('ALTER TABLE videos ADD COLUMN likes_count INTEGER DEFAULT 0;')
      }
      if (!columns.includes('comments_count')) {
        this.db.run('ALTER TABLE videos ADD COLUMN comments_count INTEGER DEFAULT 0;')
      }
      if (!columns.includes('stats_updated_at')) {
        this.db.run('ALTER TABLE videos ADD COLUMN stats_updated_at DATETIME;')
      }
    }

    this.db.run(`
      CREATE TABLE IF NOT EXISTS downloaded_videos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        url             TEXT    NOT NULL,
        title           TEXT    DEFAULT '',
        author          TEXT    DEFAULT '',
        duration        TEXT    DEFAULT '',
        quality         TEXT    DEFAULT '',
        file_path       TEXT    DEFAULT '',
        file_size       TEXT    DEFAULT '',
        thumbnail_url   TEXT    DEFAULT '',
        downloaded_at   DATETIME DEFAULT CURRENT_TIMESTAMP
      );
    `)

    this.db.run(`
      CREATE TABLE IF NOT EXISTS scraped_stories (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        url             TEXT    NOT NULL,
        title           TEXT    DEFAULT '',
        slug            TEXT    DEFAULT '',
        chapters_count  INTEGER DEFAULT 0,
        output_dir      TEXT    DEFAULT '',
        translated      INTEGER DEFAULT 0,
        published       INTEGER DEFAULT 0,
        cms_url         TEXT    DEFAULT '',
        scraped_at      DATETIME DEFAULT CURRENT_TIMESTAMP
      );
    `)

    this.db.run(`
      CREATE TABLE IF NOT EXISTS prompts (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT    NOT NULL,
        content         TEXT    NOT NULL,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
      );
    `)

    this.db.run(`
      CREATE TABLE IF NOT EXISTS settings (
        key             TEXT    PRIMARY KEY,
        value           TEXT    DEFAULT ''
      );
    `)

    const defaults = [
      ['video_dir', 'C:\\Users\\Trant\\Videos\\Seedance\\anhtonton\\AI_VIDEO'],
      ['sample_video_dir', 'C:\\Users\\Trant\\Videos\\short_drama'],
      ['theme', 'dark'],
      ['cms_url', 'https://vmnewstoryus.cfx.bz'],
      ['cms_user', 'admin'],
      ['cms_pass', '']
    ]

    for (const [k, v] of defaults) {
      this.db.run('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);', [k, v])
    }

    this.saveToDisk()
  }

  // ================= CRUD VIDEOS =================

  public getAllVideos(filter?: {
    search?: string
    status?: string
    trang_thai_video?: string
    trang_thai_dang_bai?: string
  }): VideoRow[] {
    if (!this.db) return []

    let query = 'SELECT * FROM videos WHERE 1=1'
    const params: any[] = []

    if (filter?.search) {
      const s = `%${filter.search.trim()}%`
      query +=
        ' AND (stt LIKE ? OR prompt_video LIKE ? OR content LIKE ? OR bai_goc LIKE ? OR bao_moi LIKE ?)'
      params.push(s, s, s, s, s)
    }

    if (filter?.status) {
      query += ' AND status = ?'
      params.push(filter.status)
    }

    if (filter?.trang_thai_video) {
      query += ' AND trang_thai_video = ?'
      params.push(filter.trang_thai_video)
    }

    if (filter?.trang_thai_dang_bai) {
      query += ' AND trang_thai_dang_bai = ?'
      params.push(filter.trang_thai_dang_bai)
    }

    // Natural sort by STT
    query += ' ORDER BY CAST(stt AS INTEGER) ASC, stt ASC'

    const stmt = this.db.prepare(query)
    if (params.length > 0) {
      stmt.bind(params)
    }

    const rows: VideoRow[] = []
    while (stmt.step()) {
      rows.push(stmt.getAsObject() as unknown as VideoRow)
    }
    stmt.free()
    return rows
  }

  public getVideoByStt(stt: string): VideoRow | null {
    if (!this.db) return null
    const stmt = this.db.prepare('SELECT * FROM videos WHERE stt = ? LIMIT 1;')
    stmt.bind([String(stt).trim()])
    let res: VideoRow | null = null
    if (stmt.step()) {
      res = stmt.getAsObject() as unknown as VideoRow
    }
    stmt.free()
    return res
  }

  public getNextStt(): number {
    if (!this.db) return 1
    const stmt = this.db.prepare('SELECT stt FROM videos;')
    let maxStt = 0
    while (stmt.step()) {
      const row = stmt.getAsObject()
      const sttStr = String(row.stt || '').trim()
      if (/^\d+$/.test(sttStr)) {
        const val = parseInt(sttStr, 10)
        if (val > maxStt) maxStt = val
      }
    }
    stmt.free()
    return maxStt + 1
  }

  public bulkInsertReels(urls: string[], deduplicate = true): VideoRow[] {
    if (!this.db || !urls || urls.length === 0) return []

    const cleanUrls: string[] = []
    const seen = new Set<string>()

    for (const u of urls) {
      const clean = (u || '').trim()
      if (!clean) continue
      if (deduplicate) {
        if (seen.has(clean)) continue
        seen.add(clean)
      }
      cleanUrls.push(clean)
    }

    if (cleanUrls.length === 0) return []

    const startStt = this.getNextStt()
    const now = Date.now() / 1000
    const insertedRows: VideoRow[] = []

    for (let i = 0; i < cleanUrls.length; i++) {
      const stt = String(startStt + i)
      const url = cleanUrls[i]
      const defaultSample = buildDefaultSampleVideoPath(stt)

      const row: VideoRow = {
        stt,
        status: 'FETCH VIDEO',
        trang_thai_video: 'Lấy video',
        bai_goc: url,
        video_mau: defaultSample,
        prompt_video: '',
        frame_dau_tien: '',
        bao_goc: '',
        bao_moi: '',
        trang_thai_dang_bai: 'chưa hoàn thành',
        content: '',
        link_video: '',
        bai_viet_da_dang: '',
        views_count: 0,
        likes_count: 0,
        comments_count: 0,
        stats_updated_at: '',
        local_modified: 1,
        local_modified_time: now
      }

      this.db.run(
        `INSERT INTO videos (
          stt, status, trang_thai_video, bai_goc, video_mau, prompt_video, frame_dau_tien,
          bao_goc, bao_moi, trang_thai_dang_bai, content, link_video,
          bai_viet_da_dang, views_count, likes_count, comments_count, stats_updated_at,
          local_modified, local_modified_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          stt,
          row.status || 'FETCH VIDEO',
          row.trang_thai_video || '',
          row.bai_goc || '',
          row.video_mau || '',
          row.prompt_video || '',
          row.frame_dau_tien || '',
          row.bao_goc || '',
          row.bao_moi || '',
          row.trang_thai_dang_bai || 'chưa hoàn thành',
          row.content || '',
          row.link_video || '',
          row.bai_viet_da_dang || '',
          0,
          0,
          0,
          null,
          1,
          now
        ]
      )
      insertedRows.push(row)
    }

    this.saveToDisk()
    return insertedRows
  }

  public syncStatusesWithCheck(
    items: Array<Record<string, any>>,
    checkMap: Record<string, VideoCheckResult>
  ): number {
    if (!this.db || !items || items.length === 0) return 0

    let changedCount = 0
    const now = Date.now() / 1000

    for (const item of items) {
      const stt = String(item.stt || '').trim()
      if (!stt) continue

      const oldStatus = String(item.status || item.trang_thai_video || 'FETCH VIDEO').trim()

      // User manual override FAILED must not be automatically overwritten
      if (oldStatus.toUpperCase() === STATUS_FAILED) {
        continue
      }

      const check = checkMap[stt]
      const videoExists = check ? check.exists : false
      const newStatus = determineVideoStatus(item, videoExists)

      if (newStatus !== oldStatus) {
        this.db.run(
          `UPDATE videos SET status = ?, trang_thai_video = ?, updated_at = CURRENT_TIMESTAMP, local_modified = 1, local_modified_time = ? WHERE stt = ?;`,
          [newStatus, newStatus, now, stt]
        )
        item.status = newStatus
        item.trang_thai_video = newStatus
        changedCount++
      }
    }

    if (changedCount > 0) {
      this.saveToDisk()
    }

    return changedCount
  }

  public upsertVideo(data: Record<string, any>, markLocal = true): boolean {
    if (!this.db) return false
    const stt = String(data.stt || '').trim()
    if (!stt) return false

    const existing = this.getVideoByStt(stt)
    const now = Date.now() / 1000

    // Status is respected if provided, otherwise auto-determined from fields
    const statusVal = data.status || determineVideoStatus(data)

    if (existing) {
      const updateSql = `
        UPDATE videos SET
          status = ?, trang_thai_video = ?, bai_goc = ?, video_mau = ?,
          prompt_video = ?, frame_dau_tien = ?, bao_goc = ?, bao_moi = ?,
          trang_thai_dang_bai = ?, content = ?, link_video = ?,
          bai_viet_da_dang = ?,
          views_count = ?, likes_count = ?, comments_count = ?, stats_updated_at = ?,
          updated_at = CURRENT_TIMESTAMP,
          local_modified = ?, local_modified_time = ?
        WHERE stt = ?;
      `
      this.db.run(updateSql, [
        statusVal,
        data.trang_thai_video ?? statusVal,
        data.bai_goc ?? existing.bai_goc ?? '',
        data.video_mau ?? existing.video_mau ?? '',
        data.prompt_video ?? existing.prompt_video ?? '',
        data.frame_dau_tien ?? existing.frame_dau_tien ?? '',
        data.bao_goc ?? existing.bao_goc ?? '',
        data.bao_moi ?? existing.bao_moi ?? '',
        data.trang_thai_dang_bai ?? existing.trang_thai_dang_bai ?? 'chưa hoàn thành',
        data.content ?? existing.content ?? '',
        data.link_video ?? existing.link_video ?? '',
        data.bai_viet_da_dang ?? existing.bai_viet_da_dang ?? '',
        data.views_count ?? existing.views_count ?? 0,
        data.likes_count ?? existing.likes_count ?? 0,
        data.comments_count ?? existing.comments_count ?? 0,
        data.stats_updated_at ?? existing.stats_updated_at ?? null,
        markLocal ? 1 : 0,
        markLocal ? now : existing.local_modified_time ?? 0,
        stt
      ])
    } else {
      const insertSql = `
        INSERT INTO videos (
          stt, status, trang_thai_video, bai_goc, video_mau, prompt_video, frame_dau_tien,
          bao_goc, bao_moi, trang_thai_dang_bai, content, link_video,
          bai_viet_da_dang, views_count, likes_count, comments_count, stats_updated_at,
          local_modified, local_modified_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      `
      this.db.run(insertSql, [
        stt,
        statusVal,
        data.trang_thai_video || '',
        data.bai_goc || '',
        data.video_mau || '',
        data.prompt_video || '',
        data.frame_dau_tien || '',
        data.bao_goc || '',
        data.bao_moi || '',
        data.trang_thai_dang_bai || 'chưa hoàn thành',
        data.content || '',
        data.link_video || '',
        data.bai_viet_da_dang || '',
        data.views_count ?? 0,
        data.likes_count ?? 0,
        data.comments_count ?? 0,
        data.stats_updated_at ?? null,
        markLocal ? 1 : 0,
        markLocal ? now : 0.0
      ])
    }

    this.saveToDisk()
    return true
  }

  public deleteVideo(stt: string): boolean {
    if (!this.db) return false
    const cleanStt = String(stt).trim()
    const existing = this.getVideoByStt(cleanStt)
    if (!existing) return false

    this.db.run('DELETE FROM videos WHERE stt = ?;', [cleanStt])
    this.saveToDisk()
    return true
  }

  public updateSingleField(
    stt: string,
    field: string,
    value: any,
    markLocal = true
  ): boolean {
    if (!this.db) return false
    const allowed = [
      'status',
      'trang_thai_video',
      'bai_goc',
      'video_mau',
      'prompt_video',
      'frame_dau_tien',
      'bao_goc',
      'bao_moi',
      'trang_thai_dang_bai',
      'content',
      'link_video',
      'bai_viet_da_dang',
      'views_count',
      'likes_count',
      'comments_count',
      'stats_updated_at'
    ]

    if (!allowed.includes(field)) {
      return false
    }

    const cleanStt = String(stt).trim()
    const existing = this.getVideoByStt(cleanStt)
    if (!existing) return false

    const now = Date.now() / 1000
    const sql = markLocal
      ? `UPDATE videos SET ${field} = ?, updated_at = CURRENT_TIMESTAMP, local_modified = 1, local_modified_time = ? WHERE stt = ?;`
      : `UPDATE videos SET ${field} = ?, updated_at = CURRENT_TIMESTAMP WHERE stt = ?;`

    const params = markLocal ? [value, now, cleanStt] : [value, cleanStt]
    this.db.run(sql, params)

    if (field === 'status') {
      this.db.run(
        `UPDATE videos SET trang_thai_video = ? WHERE stt = ?;`,
        [value, cleanStt]
      )
    } else if (field === 'bai_viet_da_dang') {
      if (String(existing.status || '').toUpperCase() !== STATUS_FAILED) {
        if (isPostUrl(value)) {
          this.db.run(
            `UPDATE videos SET status = ?, trang_thai_video = ?, updated_at = CURRENT_TIMESTAMP, local_modified = 1, local_modified_time = ? WHERE stt = ?;`,
            [STATUS_POSTED, STATUS_POSTED, now, cleanStt]
          )
        }
      }
    } else if (field === 'content') {
      if (String(existing.status || '').toUpperCase() !== STATUS_FAILED) {
        if (hasContentText(value) && existing.status === STATUS_VIDEO_READY) {
          this.db.run(
            `UPDATE videos SET status = ?, trang_thai_video = ?, updated_at = CURRENT_TIMESTAMP, local_modified = 1, local_modified_time = ? WHERE stt = ?;`,
            [STATUS_CONTENT_DONE, STATUS_CONTENT_DONE, now, cleanStt]
          )
        }
      }
    }

    this.saveToDisk()
    return true
  }

  public updatePostStats(
    stt: string,
    stats: { views?: number; likes?: number; comments?: number; scanned_at?: string }
  ): boolean {
    if (!this.db) return false
    const cleanStt = String(stt).trim()
    const existing = this.getVideoByStt(cleanStt)
    if (!existing) return false

    const now = Date.now() / 1000
    const views = stats.views !== undefined ? stats.views : (existing.views_count ?? 0)
    const likes = stats.likes !== undefined ? stats.likes : (existing.likes_count ?? 0)
    const comments = stats.comments !== undefined ? stats.comments : (existing.comments_count ?? 0)
    const scannedAt = stats.scanned_at || new Date().toISOString()

    this.db.run(
      `UPDATE videos SET
        views_count = ?,
        likes_count = ?,
        comments_count = ?,
        stats_updated_at = ?,
        updated_at = CURRENT_TIMESTAMP,
        local_modified = 1,
        local_modified_time = ?
      WHERE stt = ?;`,
      [views, likes, comments, scannedAt, now, cleanStt]
    )

    this.saveToDisk()
    return true
  }

  public getStatCounts(): StatCounts {
    if (!this.db) {
      return { total: 0, fetch_video: 0, video_ready: 0, content_done: 0, posted: 0, failed: 0 }
    }

    const countQuery = (where: string): number => {
      const res = this.db!.exec(`SELECT COUNT(*) FROM videos WHERE ${where};`)
      return res.length > 0 && res[0].values.length > 0 ? (res[0].values[0][0] as number) : 0
    }

    const totalRes = this.db.exec('SELECT COUNT(*) FROM videos;')
    const total = totalRes.length > 0 ? (totalRes[0].values[0][0] as number) : 0

    const fetchVideo = countQuery(
      "status = 'FETCH VIDEO' OR (status IS NULL AND (trang_thai_video != 'Xong video' OR trang_thai_video IS NULL))"
    )
    const videoReady = countQuery(
      "status = 'VIDEO READY' OR (status IS NULL AND trang_thai_video = 'Xong video')"
    )
    const contentDone = countQuery("status = 'CONTENT DONE'")
    const posted = countQuery(
      "status = 'POSTED' OR (status IS NULL AND trang_thai_dang_bai = 'hoàn thành')"
    )
    const failed = countQuery(
      "status = 'FAILED' OR trang_thai_video = 'không tạo được'"
    )

    return {
      total,
      fetch_video: fetchVideo,
      video_ready: videoReady,
      content_done: contentDone,
      posted,
      failed
    }
  }

  // ================= SETTINGS =================

  public getSetting(key: string, defaultValue = ''): string {
    if (this.settingsCache[key] !== undefined) {
      return this.settingsCache[key]
    }
    if (!this.db) return defaultValue

    const stmt = this.db.prepare('SELECT value FROM settings WHERE key = ?;')
    stmt.bind([key])
    let val = defaultValue
    if (stmt.step()) {
      val = String(stmt.getAsObject().value ?? defaultValue)
    }
    stmt.free()
    this.settingsCache[key] = val
    return val
  }

  public setSetting(key: string, value: string): void {
    const valStr = String(value)
    this.settingsCache[key] = valStr
    if (!this.db) return

    this.db.run(
      `INSERT INTO settings (key, value) VALUES (?, ?)
       ON CONFLICT(key) DO UPDATE SET value = excluded.value;`,
      [key, valStr]
    )
    this.saveToDisk()
  }

  public getAllSettings(): Record<string, string> {
    if (!this.db) return {}
    const stmt = this.db.prepare('SELECT key, value FROM settings;')
    const res: Record<string, string> = {}
    while (stmt.step()) {
      const row = stmt.getAsObject()
      res[String(row.key)] = String(row.value)
    }
    stmt.free()
    Object.assign(this.settingsCache, res)
    return res
  }

  // ================= DOWNLOADED VIDEOS =================

  public addDownloadedVideo(data: Record<string, any>): number {
    if (!this.db) return 0
    this.db.run(
      `INSERT INTO downloaded_videos (url, title, author, duration, quality, file_path, file_size, thumbnail_url)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?);`,
      [
        data.url || '',
        data.title || '',
        data.author || '',
        data.duration || '',
        data.quality || '',
        data.file_path || '',
        data.file_size || '',
        data.thumbnail_url || ''
      ]
    )
    const res = this.db.exec('SELECT last_insert_rowid();')
    this.saveToDisk()
    return res.length > 0 ? (res[0].values[0][0] as number) : 0
  }

  public getDownloadedVideos(limit = 50): DownloadedVideoItem[] {
    if (!this.db) return []
    const stmt = this.db.prepare(
      'SELECT * FROM downloaded_videos ORDER BY id DESC LIMIT ?;'
    )
    stmt.bind([limit])
    const rows: DownloadedVideoItem[] = []
    while (stmt.step()) {
      rows.push(stmt.getAsObject() as unknown as DownloadedVideoItem)
    }
    stmt.free()
    return rows
  }

  public deleteDownloadedVideo(vidId: number): void {
    if (!this.db) return
    this.db.run('DELETE FROM downloaded_videos WHERE id = ?;', [vidId])
    this.saveToDisk()
  }

  // ================= SCRAPED STORIES =================

  public addScrapedStory(data: Record<string, any>): number {
    if (!this.db) return 0
    this.db.run(
      `INSERT INTO scraped_stories (url, title, slug, chapters_count, output_dir, translated, published, cms_url)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?);`,
      [
        data.url || '',
        data.title || '',
        data.slug || '',
        data.chapters_count || 0,
        data.output_dir || '',
        data.translated || 0,
        data.published || 0,
        data.cms_url || ''
      ]
    )
    const res = this.db.exec('SELECT last_insert_rowid();')
    this.saveToDisk()
    return res.length > 0 ? (res[0].values[0][0] as number) : 0
  }

  public getScrapedStories(limit = 50): ScrapedStoryItem[] {
    if (!this.db) return []
    const stmt = this.db.prepare(
      'SELECT * FROM scraped_stories ORDER BY id DESC LIMIT ?;'
    )
    stmt.bind([limit])
    const rows: ScrapedStoryItem[] = []
    while (stmt.step()) {
      rows.push(stmt.getAsObject() as unknown as ScrapedStoryItem)
    }
    stmt.free()
    return rows
  }

  // ================= PROMPTS =================

  public getAllPrompts(): PromptItem[] {
    if (!this.db) return []
    const stmt = this.db.prepare('SELECT * FROM prompts ORDER BY id ASC;')
    const rows: PromptItem[] = []
    while (stmt.step()) {
      rows.push(stmt.getAsObject() as unknown as PromptItem)
    }
    stmt.free()
    return rows
  }

  public savePrompt(name: string, content: string, promptId?: number): number {
    if (!this.db) return 0
    if (promptId) {
      this.db.run('UPDATE prompts SET name = ?, content = ? WHERE id = ?;', [
        name,
        content,
        promptId
      ])
      this.saveToDisk()
      return promptId
    } else {
      this.db.run('INSERT INTO prompts (name, content) VALUES (?, ?);', [name, content])
      const res = this.db.exec('SELECT last_insert_rowid();')
      this.saveToDisk()
      return res.length > 0 ? (res[0].values[0][0] as number) : 0
    }
  }

  public deletePrompt(promptId: number): void {
    if (!this.db) return
    this.db.run('DELETE FROM prompts WHERE id = ?;', [promptId])
    this.saveToDisk()
  }

  // ================= CLEAR & RESET UTILITIES =================

  public clearAllVideos(): { success: boolean; count: number } {
    if (!this.db) return { success: false, count: 0 }
    const res = this.db.exec('SELECT COUNT(*) FROM videos;')
    const count = res.length > 0 ? (res[0].values[0][0] as number) : 0
    this.db.run('DELETE FROM videos;')
    try {
      this.db.run("DELETE FROM sqlite_sequence WHERE name = 'videos';")
    } catch { }
    this.saveToDisk()
    return { success: true, count }
  }

  public clearDownloadedVideos(): { success: boolean; count: number } {
    if (!this.db) return { success: false, count: 0 }
    const res = this.db.exec('SELECT COUNT(*) FROM downloaded_videos;')
    const count = res.length > 0 ? (res[0].values[0][0] as number) : 0
    this.db.run('DELETE FROM downloaded_videos;')
    try {
      this.db.run("DELETE FROM sqlite_sequence WHERE name = 'downloaded_videos';")
    } catch { }
    this.saveToDisk()
    return { success: true, count }
  }

  public clearScrapedStories(): { success: boolean; count: number } {
    if (!this.db) return { success: false, count: 0 }
    const res = this.db.exec('SELECT COUNT(*) FROM scraped_stories;')
    const count = res.length > 0 ? (res[0].values[0][0] as number) : 0
    this.db.run('DELETE FROM scraped_stories;')
    try {
      this.db.run("DELETE FROM sqlite_sequence WHERE name = 'scraped_stories';")
    } catch { }
    this.saveToDisk()
    return { success: true, count }
  }

  public clearPrompts(): { success: boolean; count: number } {
    if (!this.db) return { success: false, count: 0 }
    const res = this.db.exec('SELECT COUNT(*) FROM prompts;')
    const count = res.length > 0 ? (res[0].values[0][0] as number) : 0
    this.db.run('DELETE FROM prompts;')
    try {
      this.db.run("DELETE FROM sqlite_sequence WHERE name = 'prompts';")
    } catch { }
    this.saveToDisk()
    return { success: true, count }
  }

  public resetDatabase(options?: { keepSettings?: boolean }): {
    success: boolean
    message: string
  } {
    if (!this.db) return { success: false, message: 'Database not initialized' }

    this.db.run('DELETE FROM videos;')
    this.db.run('DELETE FROM downloaded_videos;')
    this.db.run('DELETE FROM scraped_stories;')
    this.db.run('DELETE FROM prompts;')

    if (!options?.keepSettings) {
      this.settingsCache = {}
      this.db.run('DELETE FROM settings;')
      const defaults = [
        ['video_dir', 'C:\\Users\\Trant\\Videos\\Seedance\\anhtonton\\AI_VIDEO'],
        ['sample_video_dir', 'C:\\Users\\Trant\\Videos\\short_drama'],
        ['theme', 'dark'],
        ['cms_url', 'https://vmnewstoryus.cfx.bz'],
        ['cms_user', 'admin'],
        ['cms_pass', '']
      ]
      for (const [k, v] of defaults) {
        this.db.run('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);', [k, v])
        this.settingsCache[k] = v
      }
    }

    try {
      this.db.run('DELETE FROM sqlite_sequence;')
    } catch { }

    this.saveToDisk()
    return { success: true, message: 'Reset database thành công' }
  }

  public getDatabaseStats(): {
    videosCount: number
    downloadedCount: number
    storiesCount: number
    promptsCount: number
    dbPath: string
    dbSizeBytes: number
  } {
    if (!this.db) {
      return {
        videosCount: 0,
        downloadedCount: 0,
        storiesCount: 0,
        promptsCount: 0,
        dbPath: this.dbPath,
        dbSizeBytes: 0
      }
    }

    const getCount = (tbl: string): number => {
      try {
        const res = this.db!.exec(`SELECT COUNT(*) FROM ${tbl};`)
        return res.length > 0 ? (res[0].values[0][0] as number) : 0
      } catch {
        return 0
      }
    }

    let size = 0
    if (this.dbPath && fs.existsSync(this.dbPath)) {
      try {
        size = fs.statSync(this.dbPath).size
      } catch { }
    }

    return {
      videosCount: getCount('videos'),
      downloadedCount: getCount('downloaded_videos'),
      storiesCount: getCount('scraped_stories'),
      promptsCount: getCount('prompts'),
      dbPath: this.dbPath,
      dbSizeBytes: size
    }
  }

  public close(): void {
    if (this.db) {
      this.saveToDisk()
      this.db.close()
      this.db = null
      this.initialized = false
    }
  }
}

// Singleton accessor
let dbInstance: DatabaseService | null = null

export function getDatabaseService(dbPath?: string): DatabaseService {
  if (!dbInstance) {
    dbInstance = new DatabaseService(dbPath)
  }
  return dbInstance
}
