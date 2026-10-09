/**
 * Utility helpers for In-App Browser URL cleaning, redirection unwrapping, and validation.
 * Unwraps link shims from Facebook, Instagram, Google, and YouTube so child links
 * inside posts and reels navigate cleanly without interstitial warnings.
 */

export function isValidHttpUrl(candidate: string): boolean {
  if (!candidate || typeof candidate !== 'string') return false
  const trimmed = candidate.trim()
  if (!trimmed) return false
  try {
    const parsed = new URL(trimmed)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

/**
 * Checks if a URL is an external link (like a news article, blog, story)
 * or an explicit reel/post target, rather than an internal action link.
 */
export function isExternalOrTargetLink(candidateUrl: string): boolean {
  if (!candidateUrl || typeof candidateUrl !== 'string') return false
  const trimmed = candidateUrl.trim()
  if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) return false

  try {
    const parsed = new URL(trimmed)
    const hostname = parsed.hostname.toLowerCase()

    // Redirect shims are always target navigation candidates
    if (
      hostname === 'l.facebook.com' ||
      hostname === 'lm.facebook.com' ||
      hostname === 'l.instagram.com'
    ) {
      return true
    }

    // External domains (not facebook, instagram, fb.watch)
    if (
      !hostname.endsWith('facebook.com') &&
      !hostname.endsWith('fb.watch') &&
      !hostname.endsWith('instagram.com')
    ) {
      return true
    }

    // Specific external reel/post navigation
    if (
      parsed.pathname.includes('/reel/') ||
      parsed.pathname.includes('/watch') ||
      parsed.pathname.includes('/story.php')
    ) {
      return true
    }
  } catch {
    return false
  }

  return false
}

/**
 * Extracts a valid http/https URL from a plain text comment or string,
 * trimming trailing punctuation and unwrapping any Facebook/Google redirect.
 */
export function extractUrlFromText(text: string): string | null {
  if (!text || typeof text !== 'string') return null
  const match = text.match(/https?:\/\/[^\s"'<>]+/i)
  if (!match || !match[0]) return null

  // Remove trailing punctuation common in comment sentences
  const cleanedRaw = match[0].replace(/[.,;!?)\]>]+$/, '')
  const unrolled = cleanRedirectUrl(cleanedRaw)
  if (isValidHttpUrl(unrolled)) {
    return unrolled
  }
  return null
}

/**
 * Unwraps URL redirection shims (Facebook l.php, Instagram, Google, YouTube)
 * to retrieve the real direct target URL.
 */
export function cleanRedirectUrl(rawUrl: string): string {
  if (!rawUrl || typeof rawUrl !== 'string') return ''
  const trimmed = rawUrl.trim()
  if (!trimmed) return ''

  try {
    const parsed = new URL(trimmed)
    const hostname = parsed.hostname.toLowerCase()

    // 1. Facebook redirects: l.facebook.com, lm.facebook.com, facebook.com/flx/warn, etc.
    if (
      hostname === 'l.facebook.com' ||
      hostname === 'lm.facebook.com' ||
      hostname.endsWith('.facebook.com') ||
      hostname === 'facebook.com'
    ) {
      const u = parsed.searchParams.get('u')
      if (u) {
        const direct = normalizeDestinationUrl(u)
        if (direct && isValidHttpUrl(direct)) {
          return direct
        }
      }
    }

    // 2. Instagram redirects: l.instagram.com, instagram.com/linkshim, etc.
    if (
      hostname === 'l.instagram.com' ||
      hostname.endsWith('.instagram.com') ||
      hostname === 'instagram.com'
    ) {
      const u = parsed.searchParams.get('u')
      if (u) {
        const direct = normalizeDestinationUrl(u)
        if (direct && isValidHttpUrl(direct)) {
          return direct
        }
      }
    }

    // 3. Google search & redirect shims: google.com/url?q=... or ?url=...
    if (hostname.includes('google.') && parsed.pathname.startsWith('/url')) {
      const q = parsed.searchParams.get('q') || parsed.searchParams.get('url')
      if (q) {
        const direct = normalizeDestinationUrl(q)
        if (direct && isValidHttpUrl(direct)) {
          return direct
        }
      }
    }

    // 4. YouTube redirect: youtube.com/redirect?q=...
    if (hostname.includes('youtube.com') && parsed.pathname.startsWith('/redirect')) {
      const q = parsed.searchParams.get('q')
      if (q) {
        const direct = normalizeDestinationUrl(q)
        if (direct && isValidHttpUrl(direct)) {
          return direct
        }
      }
    }
  } catch {
    // Return original trimmed if URL parsing fails
  }

  return trimmed
}

/**
 * Handles multiple layers of URL-encoding (e.g. %253A%252F%252F...)
 */
function normalizeDestinationUrl(dest: string): string {
  let url = dest.trim()
  // Guard against infinite loop with max 3 decode iterations
  for (let i = 0; i < 3; i++) {
    if (url.includes('%3A') || url.includes('%2F') || url.includes('%3a') || url.includes('%2f')) {
      try {
        const decoded = decodeURIComponent(url)
        if (decoded === url) break
        url = decoded
      } catch {
        break
      }
    } else {
      break
    }
  }
  return url
}
