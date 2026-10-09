import fs from 'fs'
import path from 'path'
import { ConfigService } from './config'

export interface VideoCheckResult {
  exists: boolean
  size: string
  bytes: number
  path: string
}

export function normalizeStt(val: any): string {
  if (val === null || val === undefined) {
    return ''
  }
  let s = String(val).trim()
  if (s.endsWith('.0')) {
    s = s.slice(0, -2)
  }
  return s
}

export function buildDefaultVideoLink(stt: string, baseDir?: string): string {
  const cleanStt = normalizeStt(stt)
  if (!cleanStt) {
    return ''
  }
  const dirPath = baseDir || ConfigService.videoDir()
  return path.normalize(path.join(dirPath, `${cleanStt}.mp4`))
}

export function buildDefaultSampleVideoPath(stt: string, baseDir?: string): string {
  const cleanStt = normalizeStt(stt)
  if (!cleanStt) {
    return ''
  }
  const dirPath = baseDir || ConfigService.sampleVideoDir()
  return path.normalize(path.join(dirPath, `${cleanStt}.mp4`))
}

export function formatBytes(sz: number): string {
  const mb = sz / (1024 * 1024)
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(sz / 1024)} KB`
}

export function checkVideoFile(
  pathStr: string,
  stt?: string,
  baseDir?: string
): VideoCheckResult {
  let targetPath = (pathStr || '').trim().replace(/^["']|["']$/g, '')
  if (!targetPath && stt) {
    targetPath = buildDefaultVideoLink(stt, baseDir)
  }

  if (!targetPath) {
    return { exists: false, size: '', bytes: 0, path: '' }
  }

  if (fs.existsSync(targetPath)) {
    try {
      const stat = fs.statSync(targetPath)
      if (stat.isFile()) {
        return { exists: true, size: formatBytes(stat.size), bytes: stat.size, path: targetPath }
      }
    } catch {
      return { exists: true, size: 'Có sẵn', bytes: 0, path: targetPath }
    }
  }

  if (stt) {
    const defaultP = buildDefaultVideoLink(stt, baseDir)
    if (defaultP !== targetPath && fs.existsSync(defaultP)) {
      try {
        const stat = fs.statSync(defaultP)
        if (stat.isFile()) {
          return { exists: true, size: formatBytes(stat.size), bytes: stat.size, path: defaultP }
        }
      } catch {
        return { exists: true, size: 'Có sẵn', bytes: 0, path: defaultP }
      }
    }
  }

  return { exists: false, size: '', bytes: 0, path: targetPath }
}

export function checkVideoFilesBatch(
  items: Array<Record<string, any>>,
  baseDir?: string
): Record<string, VideoCheckResult> {
  const targetDir = baseDir || ConfigService.videoDir()
  const fileMap = new Map<string, { path: string; bytes: number; size: string }>()

  if (fs.existsSync(targetDir)) {
    try {
      const entries = fs.readdirSync(targetDir, { withFileTypes: true })
      for (const entry of entries) {
        if (entry.isFile()) {
          const nameLower = entry.name.toLowerCase()
          const fullPath = path.join(targetDir, entry.name)
          try {
            const stat = fs.statSync(fullPath)
            fileMap.set(nameLower, {
              path: fullPath,
              bytes: stat.size,
              size: formatBytes(stat.size)
            })
          } catch {
            fileMap.set(nameLower, {
              path: fullPath,
              bytes: 0,
              size: 'Có sẵn'
            })
          }
        }
      }
    } catch (e) {
      console.warn(`[checkVideoFilesBatch] Scan dir warning: ${e}`)
    }
  }

  const results: Record<string, VideoCheckResult> = {}
  for (const item of items) {
    const stt = normalizeStt(item.stt)
    if (!stt) continue

    const linkV = (item.link_video || '').trim().replace(/^["']|["']$/g, '')
    let found = false

    if (linkV) {
      const linkName = path.basename(linkV).toLowerCase()
      if (
        fileMap.has(linkName) &&
        path.dirname(path.normalize(linkV)).toLowerCase() === path.normalize(targetDir).toLowerCase()
      ) {
        const cached = fileMap.get(linkName)!
        results[stt] = { exists: true, size: cached.size, bytes: cached.bytes, path: cached.path }
        found = true
      } else if (fs.existsSync(linkV)) {
        try {
          const stat = fs.statSync(linkV)
          if (stat.isFile()) {
            results[stt] = { exists: true, size: formatBytes(stat.size), bytes: stat.size, path: linkV }
            found = true
          }
        } catch {
          results[stt] = { exists: true, size: 'Có sẵn', bytes: 0, path: linkV }
          found = true
        }
      }
    }

    if (!found) {
      const defName = `${stt}.mp4`.toLowerCase()
      if (fileMap.has(defName)) {
        const cached = fileMap.get(defName)!
        results[stt] = { exists: true, size: cached.size, bytes: cached.bytes, path: cached.path }
      } else {
        const defaultP = targetDir ? path.normalize(path.join(targetDir, `${stt}.mp4`)) : ''
        results[stt] = { exists: false, size: '', bytes: 0, path: linkV || defaultP }
      }
    }
  }

  return results
}

export function checkSampleVideoFile(
  pathStr: string,
  stt?: string,
  baseDir?: string
): VideoCheckResult {
  let targetPath = (pathStr || '').trim().replace(/^["']|["']$/g, '')
  if (!targetPath && stt) {
    targetPath = buildDefaultSampleVideoPath(stt, baseDir)
  }

  if (!targetPath) {
    return { exists: false, size: '', bytes: 0, path: '' }
  }

  if (fs.existsSync(targetPath)) {
    try {
      const stat = fs.statSync(targetPath)
      if (stat.isFile()) {
        return { exists: true, size: formatBytes(stat.size), bytes: stat.size, path: targetPath }
      }
    } catch {
      return { exists: true, size: 'Có sẵn', bytes: 0, path: targetPath }
    }
  }

  if (stt) {
    const defaultP = buildDefaultSampleVideoPath(stt, baseDir)
    if (defaultP !== targetPath && fs.existsSync(defaultP)) {
      try {
        const stat = fs.statSync(defaultP)
        if (stat.isFile()) {
          return { exists: true, size: formatBytes(stat.size), bytes: stat.size, path: defaultP }
        }
      } catch {
        return { exists: true, size: 'Có sẵn', bytes: 0, path: defaultP }
      }
    }
  }

  return { exists: false, size: '', bytes: 0, path: targetPath }
}

export function checkSampleVideosBatch(
  items: Array<Record<string, any>>,
  baseDir?: string
): Record<string, VideoCheckResult> {
  const targetDir = baseDir || ConfigService.sampleVideoDir()
  const fileMap = new Map<string, { path: string; bytes: number; size: string }>()

  if (fs.existsSync(targetDir)) {
    try {
      const entries = fs.readdirSync(targetDir, { withFileTypes: true })
      for (const entry of entries) {
        if (entry.isFile()) {
          const nameLower = entry.name.toLowerCase()
          const fullPath = path.join(targetDir, entry.name)
          try {
            const stat = fs.statSync(fullPath)
            fileMap.set(nameLower, {
              path: fullPath,
              bytes: stat.size,
              size: formatBytes(stat.size)
            })
          } catch {
            fileMap.set(nameLower, {
              path: fullPath,
              bytes: 0,
              size: 'Có sẵn'
            })
          }
        }
      }
    } catch (e) {
      console.warn(`[checkSampleVideosBatch] Scan dir warning: ${e}`)
    }
  }

  const results: Record<string, VideoCheckResult> = {}
  for (const item of items) {
    const stt = normalizeStt(item.stt)
    if (!stt) continue

    const vmPath = (item.video_mau || '').trim().replace(/^["']|["']$/g, '')
    let found = false

    if (vmPath) {
      const vmName = path.basename(vmPath).toLowerCase()
      if (
        fileMap.has(vmName) &&
        path.dirname(path.normalize(vmPath)).toLowerCase() === path.normalize(targetDir).toLowerCase()
      ) {
        const cached = fileMap.get(vmName)!
        results[stt] = { exists: true, size: cached.size, bytes: cached.bytes, path: cached.path }
        found = true
      } else if (fs.existsSync(vmPath)) {
        try {
          const stat = fs.statSync(vmPath)
          if (stat.isFile()) {
            results[stt] = { exists: true, size: formatBytes(stat.size), bytes: stat.size, path: vmPath }
            found = true
          }
        } catch {
          results[stt] = { exists: true, size: 'Có sẵn', bytes: 0, path: vmPath }
          found = true
        }
      }
    }

    if (!found) {
      const defName = `${stt}.mp4`.toLowerCase()
      if (fileMap.has(defName)) {
        const cached = fileMap.get(defName)!
        results[stt] = { exists: true, size: cached.size, bytes: cached.bytes, path: cached.path }
      } else {
        const defaultP = targetDir ? path.normalize(path.join(targetDir, `${stt}.mp4`)) : ''
        results[stt] = { exists: false, size: '', bytes: 0, path: vmPath || defaultP }
      }
    }
  }

  return results
}
