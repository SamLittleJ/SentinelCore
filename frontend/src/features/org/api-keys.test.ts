import { describe, expect, it } from 'vitest'

import { makeApiKey } from '@/test/server'

import { keyState, sourceProblem, validKeyName } from './api-keys'

const NOW = Date.parse('2026-10-09T12:00:00Z')

describe('API key state', () => {
  it('is active until it expires or is revoked', () => {
    expect(keyState(makeApiKey({ expires_at: '2026-11-01T00:00:00Z' }), NOW)).toBe('active')
    expect(keyState(makeApiKey({ expires_at: '2026-10-09T12:00:00Z' }), NOW)).toBe('expired')
  })

  it('stays revoked after it would have expired', () => {
    const key = makeApiKey({
      expires_at: '2026-10-01T00:00:00Z',
      revoked_at: '2026-09-20T00:00:00Z',
    })
    expect(keyState(key, NOW)).toBe('revoked')
  })
})

describe('new key validation', () => {
  it('accepts the sources the API accepts, as it stores them', () => {
    for (const source of ['vpn', 'k8s-audit', 'GitHub', ' okta.prod ', 'a_b']) {
      expect(sourceProblem(source)).toBeNull()
    }
  })

  it('rejects malformed sources', () => {
    for (const source of ['', 'v', '-vpn', 'vpn!', 'my vpn', 'x'.repeat(51)]) {
      expect(sourceProblem(source)).toBe('format')
    }
  })

  it('rejects the sources the application keeps for itself', () => {
    expect(sourceProblem('backend')).toBe('reserved')
    expect(sourceProblem(' Detection ')).toBe('reserved')
  })

  it('needs a name of 3 to 100 characters', () => {
    expect(validKeyName('  ab ')).toBe(false)
    expect(validKeyName('VPN')).toBe(true)
    expect(validKeyName('x'.repeat(101))).toBe(false)
  })
})
