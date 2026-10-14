import { describe, expect, it } from 'vitest'

import { developmentHeaders, productionHeaders } from './security-headers'
import config from './vite.config'

function directives(policy: string): Record<string, string[]> {
  return Object.fromEntries(
    policy.split(';').map((directive) => {
      const [name, ...sources] = directive.trim().split(/\s+/)
      return [name, sources]
    }),
  )
}

const production = directives(productionHeaders['Content-Security-Policy'])
const development = directives(developmentHeaders['Content-Security-Policy'])

describe('security headers', () => {
  it('runs only the bundle’s own scripts in production', () => {
    expect(production['script-src']).toEqual(["'self'"])
    expect(production['default-src']).toEqual(["'self'"])
    expect(production['object-src']).toEqual(["'none'"])
    expect(production['base-uri']).toEqual(["'none'"])
    expect(production['connect-src']).toEqual(["'self'"])
    expect(production['form-action']).toEqual(["'self'"])
  })

  it('allows inline styles but no other inline content', () => {
    expect(production['style-src']).toEqual(["'self'", "'unsafe-inline'"])
    for (const [name, sources] of Object.entries(production)) {
      if (name !== 'style-src') expect(sources, name).not.toContain("'unsafe-inline'")
      expect(sources, name).not.toContain("'unsafe-eval'")
    }
  })

  it('lets no other site frame the console', () => {
    for (const headers of [productionHeaders, developmentHeaders]) {
      expect(directives(headers['Content-Security-Policy'])['frame-ancestors']).toEqual(["'none'"])
      expect(headers['X-Frame-Options']).toBe('DENY')
      expect(headers['X-Content-Type-Options']).toBe('nosniff')
      expect(headers['Referrer-Policy']).toBe('no-referrer')
      expect(headers['Cross-Origin-Opener-Policy']).toBe('same-origin')
    }
  })

  it('relaxes only what the dev server needs', () => {
    expect(development['script-src']).toEqual(["'self'", "'unsafe-inline'"])
    expect(development['connect-src']).toEqual(["'self'", 'ws:'])
    expect(Object.keys(development)).toEqual(Object.keys(production))
    for (const name of Object.keys(production)) {
      if (name === 'script-src' || name === 'connect-src') continue
      expect(development[name], name).toEqual(production[name])
    }
  })

  it('is what the dev server and the preview of the build send', () => {
    expect(config.server?.headers).toBe(developmentHeaders)
    expect(config.preview?.headers).toBe(productionHeaders)
  })

  it('keeps fonts as files, which font-src allows, never as data: URIs', () => {
    const inline = config.build?.assetsInlineLimit
    if (typeof inline !== 'function') throw new Error('assetsInlineLimit is not a function')
    expect(inline('/fonts/ibm-plex-sans-condensed-cyrillic-ext-600-normal.woff2', Buffer.alloc(100))).toBe(false)
    expect(inline('/fonts/ibm-plex-sans-condensed-cyrillic-ext-600-normal.woff', Buffer.alloc(100))).toBe(false)
    expect(inline('/icons/shield.svg', Buffer.alloc(100))).toBeUndefined()
  })
})
