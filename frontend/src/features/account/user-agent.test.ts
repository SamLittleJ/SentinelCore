import { describe, expect, it } from 'vitest'

import { describeUserAgent } from './user-agent'

describe('describeUserAgent', () => {
  it.each([
    [
      'Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0',
      { browser: 'Firefox', os: 'Linux', kind: 'desktop' },
    ],
    [
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
      { browser: 'Edge', os: 'Windows', kind: 'desktop' },
    ],
    [
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15',
      { browser: 'Safari', os: 'macOS', kind: 'desktop' },
    ],
    [
      'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/141.0 Mobile/15E148 Safari/604.1',
      { browser: 'Chrome', os: 'iOS', kind: 'mobile' },
    ],
    [
      'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
      { browser: 'Chrome', os: 'Android', kind: 'mobile' },
    ],
    [
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 OPR/122.0.0.0',
      { browser: 'Opera', os: 'Windows', kind: 'desktop' },
    ],
  ])('recognizes %s', (userAgent, expected) => {
    expect(describeUserAgent(userAgent)).toEqual(expected)
  })

  it('leaves tools and scripts unnamed', () => {
    expect(describeUserAgent('python-httpx/0.28.1')).toEqual({
      browser: null,
      os: null,
      kind: 'unknown',
    })
  })

  it('handles a missing header', () => {
    expect(describeUserAgent(null)).toEqual({ browser: null, os: null, kind: 'unknown' })
  })
})
