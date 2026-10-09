import fs from 'fs'
import path from 'path'
import crypto from 'crypto'
import { execSync } from 'child_process'
import axios from 'axios'

const SECRET_SALT = 'STORY_SCRAPER_SECRET_KEY_2026_@#!%987'
const DEFAULT_SHEET_URL =
  'https://docs.google.com/spreadsheets/d/1WKYyFFyURvMXY5pgzlJw_S56sBxrHEqYEdyMfMFgMNA/export?format=csv'

export function normalizeHwid(hwidStr: string): string {
  return String(hwidStr || '')
    .replace(/[^A-Za-z0-9]/g, '')
    .toUpperCase()
}

export function normalizeSheetUrl(url: string): string {
  const clean = (url || '').trim()
  if (!clean) return ''

  if (clean.includes('/pubhtml')) {
    return clean.replace('/pubhtml', '/pub?output=csv')
  }
  if (clean.includes('/pub') && !clean.includes('output=csv')) {
    const sep = clean.includes('?') ? '&' : '?'
    return `${clean}${sep}output=csv`
  }

  const match = clean.match(/https:\/\/docs\.google\.com\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/)
  if (match && !clean.includes('/pub')) {
    const docId = match[1]
    const gidMatch = clean.match(/[#&?]gid=([0-9]+)/)
    const gid = gidMatch ? gidMatch[1] : '0'
    return `https://docs.google.com/spreadsheets/d/${docId}/export?format=csv&gid=${gid}`
  }

  return clean
}

export function parseExpireDate(dateStr: string): Date | null {
  if (!dateStr) return null
  const d = dateStr.trim().toLowerCase()
  if (
    [
      'vĩnh viễn',
      'vinh vien',
      'forever',
      'lifetime',
      'unlimited',
      'trọn đời',
      'tron doi',
      'none',
      ''
    ].includes(d)
  ) {
    return null
  }

  // formats: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD
  const parts = d.split(/[-/]/)
  if (parts.length === 3) {
    let year = 0
    let month = 0
    let day = 0
    if (parts[0].length === 4) {
      // YYYY-MM-DD
      year = parseInt(parts[0], 10)
      month = parseInt(parts[1], 10) - 1
      day = parseInt(parts[2], 10)
    } else {
      // DD-MM-YYYY
      day = parseInt(parts[0], 10)
      month = parseInt(parts[1], 10) - 1
      year = parseInt(parts[2], 10)
    }

    if (isNaN(year) || isNaN(month) || isNaN(day)) return null
    const dateObj = new Date(year, month, day)
    return isNaN(dateObj.getTime()) ? null : dateObj
  }

  return null
}

export function signCachePayload(data: Record<string, any>): string {
  const msg = `${data.hwid}:${data.user}:${data.expires}:${data.verified_at}`
  return crypto
    .createHmac('sha256', SECRET_SALT)
    .update(msg)
    .digest('hex')
    .slice(0, 16)
}

let cachedMachineId = ''

export function getMachineId(): string {
  if (cachedMachineId) return cachedMachineId

  let rawId = ''
  try {
    if (process.platform === 'win32') {
      const out = execSync(
        'powershell -NoProfile -Command "(Get-CimInstance Win32_ComputerSystemProduct).UUID"',
        { timeout: 5000, encoding: 'utf-8' }
      ).trim()
      if (out && !out.includes('UUID') && out.length >= 8) {
        rawId = out
      } else {
        const out2 = execSync(
          'powershell -NoProfile -Command "(Get-CimInstance Win32_BIOS).SerialNumber"',
          { timeout: 5000, encoding: 'utf-8' }
        ).trim()
        rawId = out2
      }
    } else if (process.platform === 'darwin') {
      rawId = execSync(
        "ioreg -rd1 -c IOPlatformExpertDevice | awk '/IOPlatformUUID/ { print $3; }'",
        { timeout: 5000, encoding: 'utf-8' }
      )
        .replace(/"/g, '')
        .trim()
    } else {
      if (fs.existsSync('/etc/machine-id')) {
        rawId = fs.readFileSync('/etc/machine-id', 'utf-8').trim()
      }
    }
  } catch {}

  if (!rawId) {
    rawId = process.env.COMPUTERNAME || process.env.HOSTNAME || 'DEFAULT_MACHINE_ID'
  }

  const hashed = crypto
    .createHash('sha256')
    .update(`${rawId}_SCAN_STORY_DEVICE_2026`)
    .digest('hex')
    .toUpperCase()

  cachedMachineId = `${hashed.slice(0, 4)}-${hashed.slice(4, 8)}-${hashed.slice(8, 12)}`
  return cachedMachineId
}

export interface LicenseStatus {
  valid: boolean
  message: string
  user?: string
  expires?: string
  days_left?: number
  hwid: string
  source?: 'online' | 'cache'
  code?: string
}

export class LicenseManager {
  private static cacheFile = path.join(process.cwd(), '.license_cache')

  public static async verifyLicense(sheetUrl?: string): Promise<LicenseStatus> {
    const hwid = getMachineId()
    const targetHwidClean = normalizeHwid(hwid)
    const targetUrl = normalizeSheetUrl(sheetUrl || DEFAULT_SHEET_URL)

    try {
      const cbUrl = `${targetUrl}${targetUrl.includes('?') ? '&' : '?'}_cb=${Date.now()}`
      const response = await axios.get(cbUrl, {
        timeout: 8000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
          'Cache-Control': 'no-cache, no-store, must-revalidate'
        }
      })

      if (response.status === 200 && response.data) {
        const text = String(response.data)
        const lines = text.split(/\r?\n/)

        for (const line of lines) {
          const cols = line.split(',').map((c) => c.replace(/^["']|["']$/g, '').trim())
          if (cols.length >= 2) {
            const lineHwid = normalizeHwid(cols[0])
            if (lineHwid && lineHwid === targetHwidClean) {
              const userName = cols[1] || 'User'
              const expireStr = cols[2] || 'Vĩnh viễn'
              const statusStr = (cols[3] || 'Active').toLowerCase()

              if (statusStr.includes('block') || statusStr.includes('khoá') || statusStr.includes('hủy')) {
                return {
                  valid: false,
                  message: 'Thiết bị của bạn đã bị quản trị viên khóa bản quyền.',
                  hwid,
                  code: 'LOCKED'
                }
              }

              const expDate = parseExpireDate(expireStr)
              const today = new Date()
              today.setHours(0, 0, 0, 0)

              if (expDate && today > expDate) {
                return {
                  valid: false,
                  message: `Bản quyền đã hết hạn vào ngày ${expireStr}.`,
                  hwid,
                  code: 'EXPIRED'
                }
              }

              const daysLeft = expDate
                ? Math.ceil((expDate.getTime() - today.getTime()) / (1000 * 3600 * 24))
                : 9999

              // Save to cache
              this.saveCache({ hwid, user: userName, expires: expireStr })

              return {
                valid: true,
                message: 'Bản quyền hợp lệ (Đã xác thực trực tuyến).',
                user: userName,
                expires: expireStr,
                days_left: daysLeft,
                hwid,
                source: 'online'
              }
            }
          }
        }

        return {
          valid: false,
          message: 'Mã máy chưa được đăng ký trong danh sách bản quyền.',
          hwid,
          code: 'UNREGISTERED'
        }
      }
    } catch (err) {
      console.warn(`[LicenseManager] Online check failed, falling back to cache: ${err}`)
    }

    // Fallback to offline cache
    const cached = this.loadCache(hwid)
    if (cached) return cached

    return {
      valid: false,
      message: 'Không thể kết nối máy chủ xác thực và không tìm thấy bản quyền offline.',
      hwid,
      code: 'OFFLINE_FAIL'
    }
  }

  private static saveCache(data: { hwid: string; user: string; expires: string }): void {
    try {
      const payload: Record<string, any> = {
        ...data,
        verified_at: new Date().toISOString()
      }
      payload.sig = signCachePayload(payload)
      fs.writeFileSync(this.cacheFile, JSON.stringify(payload, null, 2), 'utf-8')
    } catch {}
  }

  private static loadCache(hwid: string, maxHours = 48): LicenseStatus | null {
    if (!fs.existsSync(this.cacheFile)) return null
    try {
      const raw = fs.readFileSync(this.cacheFile, 'utf-8')
      const data = JSON.parse(raw)
      const sig = data.sig
      delete data.sig

      if (signCachePayload(data) !== sig) return null
      if (normalizeHwid(data.hwid) !== normalizeHwid(hwid)) return null

      const verifiedAt = new Date(data.verified_at)
      if (Date.now() - verifiedAt.getTime() > maxHours * 3600 * 1000) {
        return null
      }

      const expDate = parseExpireDate(data.expires)
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      if (expDate && today > expDate) return null

      const daysLeft = expDate
        ? Math.ceil((expDate.getTime() - today.getTime()) / (1000 * 3600 * 24))
        : 9999

      return {
        valid: true,
        message: 'Bản quyền hợp lệ (Chế độ Offline).',
        user: data.user,
        expires: data.expires,
        days_left: daysLeft,
        hwid,
        source: 'cache'
      }
    } catch {
      return null
    }
  }
}
