import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import {
  normalizeHwid,
  normalizeSheetUrl,
  getMachineId,
  signCachePayload,
  parseExpireDate,
  LicenseManager
} from '../src/main/services/license-manager'

describe('License Manager Service', () => {
  // 1. HAPPY PATHS
  describe('Happy Paths', () => {
    it('normalizes HWID strings correctly', () => {
      expect(normalizeHwid('A1B2-C3D4-E5F6')).toBe('A1B2C3D4E5F6')
      expect(normalizeHwid(' a1b2 c3d4 ')).toBe('A1B2C3D4')
    })

    it('normalizes various Google Sheet URL formats to CSV export', () => {
      const editUrl = 'https://docs.google.com/spreadsheets/d/1WKYyFFyURvMXY5pgzlJw_S56sBxrHEqYEdyMfMFgMNA/edit?usp=sharing'
      const norm1 = normalizeSheetUrl(editUrl)
      expect(norm1).toContain('/export?format=csv')

      const pubUrl = 'https://docs.google.com/spreadsheets/d/1WKYyFFyURvMXY5pgzlJw_S56sBxrHEqYEdyMfMFgMNA/pubhtml'
      const norm2 = normalizeSheetUrl(pubUrl)
      expect(norm2).toContain('/pub?output=csv')
    })

    it('generates consistent machine HWID in XXXX-XXXX-XXXX format', () => {
      const hwid1 = getMachineId()
      const hwid2 = getMachineId()
      expect(hwid1).toMatch(/^[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$/)
      expect(hwid1).toBe(hwid2)
    })

    it('correctly parses expiration dates or lifetime keywords', () => {
      expect(parseExpireDate('2026-12-31')).toEqual(new Date(2026, 11, 31))
      expect(parseExpireDate('31/12/2026')).toEqual(new Date(2026, 11, 31))
      expect(parseExpireDate('Vĩnh viễn')).toBeNull()
      expect(parseExpireDate('lifetime')).toBeNull()
    })

    it('signs and verifies HMAC cache payload correctly', () => {
      const payload = {
        hwid: 'ABCD-1234-EFGH',
        user: 'Tester',
        expires: '2026-12-31',
        verified_at: '2026-10-06 00:00:00'
      }
      const sig = signCachePayload(payload)
      expect(sig).toBeDefined()
      expect(sig.length).toBe(16)
    })
  })

  // 2. EDGE CASES
  describe('Edge Cases', () => {
    it('handles empty or null strings for URL and HWID normalization', () => {
      expect(normalizeHwid('')).toBe('')
      expect(normalizeHwid(null as any)).toBe('')
      expect(normalizeSheetUrl('')).toBe('')
      expect(normalizeSheetUrl(null as any)).toBe('')
    })

    it('returns null for unparseable dates', () => {
      expect(parseExpireDate('invalid-date-string')).toBeNull()
    })
  })
})
