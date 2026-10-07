import { describe, expect, it } from 'vitest'

import { formatRelative } from './format'

const NOW = Date.parse('2026-10-06T12:00:00Z')
const ago = (ms: number) => new Date(NOW - ms).toISOString()

describe('formatRelative', () => {
  it.each([
    [ago(20_000), 'acum'],
    [ago(5 * 60_000), 'acum 5 minute'],
    [ago(3 * 60 * 60_000), 'acum 3 ore'],
    [ago(24 * 60 * 60_000), 'ieri'],
    [new Date(NOW + 25 * 60_000).toISOString(), 'peste 25 de minute'],
  ])('describes %s as "%s"', (value, expected) => {
    expect(formatRelative(value, 'ro', NOW)).toBe(expected)
  })

  it('switches to the date after a month', () => {
    expect(formatRelative('2026-08-01T09:00:00Z', 'ro', NOW)).toBe('1 aug. 2026')
  })

  it('follows the interface language', () => {
    expect(formatRelative(ago(5 * 60_000), 'en', NOW)).toBe('5 minutes ago')
  })
})
