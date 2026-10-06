export type DeviceKind = 'desktop' | 'mobile' | 'unknown'

export interface DeviceDescription {
  browser: string | null
  os: string | null
  kind: DeviceKind
}

// Order matters: Edge and Opera also announce Chrome, Chrome also announces
// Safari, so the more specific tokens are checked first.
const BROWSERS: [RegExp, string][] = [
  [/Edg(?:e|A|iOS)?\//, 'Edge'],
  [/OPR\/|Opera/, 'Opera'],
  [/Firefox\/|FxiOS\//, 'Firefox'],
  [/Chrome\/|CriOS\//, 'Chrome'],
  [/Safari\//, 'Safari'],
]

const OPERATING_SYSTEMS: [RegExp, string, DeviceKind][] = [
  [/Android/, 'Android', 'mobile'],
  [/iPhone|iPad|iPod/, 'iOS', 'mobile'],
  [/Windows/, 'Windows', 'desktop'],
  [/CrOS/, 'ChromeOS', 'desktop'],
  [/Mac OS X|Macintosh/, 'macOS', 'desktop'],
  [/Linux/, 'Linux', 'desktop'],
]

/**
 * A readable guess at the device behind a session. The header is set by the
 * client and can claim anything, so this is a hint, never an identity.
 */
export function describeUserAgent(userAgent: string | null): DeviceDescription {
  if (!userAgent) {
    return { browser: null, os: null, kind: 'unknown' }
  }
  const browser = BROWSERS.find(([pattern]) => pattern.test(userAgent))?.[1] ?? null
  const os = OPERATING_SYSTEMS.find(([pattern]) => pattern.test(userAgent))
  return { browser, os: os?.[1] ?? null, kind: os?.[2] ?? 'unknown' }
}
