import { describe, expect, it } from 'vitest'

import { hasUserFilters, readUserFilters, writeUserFilters } from './user-filters'

describe('user list filters', () => {
  it('reads the address, ignoring unknown roles and states', () => {
    const filters = readUserFilters(
      new URLSearchParams('q=%20pop%20&role=admin&role=root&role=owner&state=asleep'),
    )
    expect(filters).toEqual({ search: 'pop', roles: ['admin', 'owner'], state: undefined })
  })

  it('writes only what narrows the list, and reads it back unchanged', () => {
    expect(writeUserFilters({ search: '', roles: [] }).toString()).toBe('')

    const filters = { search: 'pop', roles: ['security_analyst' as const], state: 'locked' as const }
    const params = writeUserFilters(filters)
    expect(params.toString()).toBe('q=pop&role=security_analyst&state=locked')
    expect(readUserFilters(params)).toEqual(filters)
  })

  it('knows when the list is narrowed', () => {
    expect(hasUserFilters({ search: '', roles: [] })).toBe(false)
    expect(hasUserFilters({ search: '', roles: [], state: 'inactive' })).toBe(true)
    expect(hasUserFilters({ search: 'a', roles: [] })).toBe(true)
    expect(hasUserFilters({ search: '', roles: ['user'] })).toBe(true)
  })
})
