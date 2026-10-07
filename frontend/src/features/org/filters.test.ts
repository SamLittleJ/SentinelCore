import { describe, expect, it } from 'vitest'

import { SECURITY_EVENT_TYPES } from '@/features/account/api'

import {
  DEFAULT_RANGE,
  hasNarrowingFilters,
  readLogFilters,
  searchQuery,
  sinceFor,
  writeLogFilters,
} from './filters'

describe('log filters in the address', () => {
  it('reads every filter', () => {
    const params = new URLSearchParams(
      'range=24h&type=login_failed&type=account_locked&severity=warn&q=%20ana@example.com%20&user=5&target=7',
    )

    expect(readLogFilters(params, SECURITY_EVENT_TYPES)).toEqual({
      range: '24h',
      types: ['login_failed', 'account_locked'],
      severities: ['warn'],
      search: 'ana@example.com',
      userId: 5,
      targetUserId: 7,
    })
  })

  it('ignores values that are not valid', () => {
    const params = new URLSearchParams(
      'range=1y&type=not_a_type&severity=critical&user=0&target=abc',
    )

    expect(readLogFilters(params, SECURITY_EVENT_TYPES)).toEqual({
      range: DEFAULT_RANGE,
      types: [],
      severities: [],
      search: '',
      userId: undefined,
      targetUserId: undefined,
    })
  })

  it('writes filters back without the defaults', () => {
    const filters = readLogFilters(new URLSearchParams('type=login_failed&user=5'), SECURITY_EVENT_TYPES)

    expect(writeLogFilters(filters).toString()).toBe('type=login_failed&user=5')
    expect(writeLogFilters({ ...filters, types: [], userId: undefined }).toString()).toBe('')
  })

  it('tells whether anything narrows the log beyond the time range', () => {
    const none = readLogFilters(new URLSearchParams('range=1h'), SECURITY_EVENT_TYPES)

    expect(hasNarrowingFilters(none)).toBe(false)
    expect(hasNarrowingFilters({ ...none, targetUserId: 3 })).toBe(true)
  })
})

describe('time ranges', () => {
  it('measures the start back from now', () => {
    const now = Date.parse('2026-10-07T12:00:00Z')

    expect(sinceFor('1h', now)).toBe('2026-10-07T11:00:00.000Z')
    expect(sinceFor('7d', now)).toBe('2026-09-30T12:00:00.000Z')
    expect(sinceFor('all', now)).toBeUndefined()
  })
})

describe('search', () => {
  it.each([
    ['203.0.113.9', { ipAddress: '203.0.113.9' }],
    ['2001:db8::1', { ipAddress: '2001:db8::1' }],
    ['ana@example.com', { email: 'ana@example.com' }],
    ['', {}],
  ])('sends %j to the right filter', (search, expected) => {
    expect(searchQuery(search)).toEqual(expected)
  })
})
