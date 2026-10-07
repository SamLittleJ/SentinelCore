import { describe, expect, it } from 'vitest'

import { safeNextPath } from './redirect'

describe('safeNextPath', () => {
  it.each(['/me', '/org/events?severity=incident', '/me/sessions'])('keeps app path %s', (path) => {
    expect(safeNextPath(path)).toBe(path)
  })

  it.each([
    null,
    '',
    'https://evil.example',
    '//evil.example',
    '/\\evil.example',
    'javascript:alert(1)',
    'me',
    '/login',
    '/login?next=/me',
  ])('falls back to /me for %s', (next) => {
    expect(safeNextPath(next)).toBe('/me')
  })
})
