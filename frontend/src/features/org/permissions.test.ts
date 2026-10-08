import { describe, expect, it } from 'vitest'

import type { Role } from '@/features/auth/api'
import { makeUser } from '@/test/server'

import { accountActions, isLockedNow } from './permissions'

const NOW = Date.parse('2026-10-08T12:00:00Z')
const lockedUntil = (offsetMs: number) => new Date(NOW + offsetMs).toISOString()

const actor = (role: Role) => makeUser(role, { id: 1 })
const target = (role: Role, overrides = {}) => makeUser(role, { id: 2, ...overrides })

describe('account lock state', () => {
  it('counts a lock only while it is in force', () => {
    expect(isLockedNow(target('user'), NOW)).toBe(false)
    expect(isLockedNow(target('user', { locked_until: lockedUntil(1000) }), NOW)).toBe(true)
    expect(isLockedNow(target('user', { locked_until: lockedUntil(0) }), NOW)).toBe(false)
  })
})

describe('account actions', () => {
  it('gives nobody actions on their own account or on an owner', () => {
    const owner = actor('owner')
    expect(accountActions(owner, owner, NOW)).toMatchObject({ restriction: 'self' })
    expect(accountActions(actor('admin'), target('owner'), NOW)).toMatchObject({ restriction: 'owner' })
  })

  it('lets the analyst contain any other account, but not unlock or manage it', () => {
    const locked = target('admin', { locked_until: lockedUntil(1000) })
    expect(accountActions(actor('security_analyst'), locked, NOW).actions).toEqual({
      revokeSessions: true,
      lock: true,
      unlock: false,
      changeStatus: false,
      changeRole: false,
    })
  })

  it('offers unlocking only while a lock is in force', () => {
    const admin = actor('admin')
    expect(accountActions(admin, target('user'), NOW).actions.unlock).toBe(false)
    expect(
      accountActions(admin, target('user', { locked_until: lockedUntil(-1000) }), NOW).actions.unlock,
    ).toBe(false)
    expect(
      accountActions(admin, target('user', { locked_until: lockedUntil(1000) }), NOW).actions.unlock,
    ).toBe(true)
  })

  it("leaves an admin's status to the owner, and roles to the owner alone", () => {
    expect(accountActions(actor('admin'), target('security_analyst'), NOW).actions).toMatchObject({
      changeStatus: true,
      changeRole: false,
    })
    expect(accountActions(actor('admin'), target('admin'), NOW).actions.changeStatus).toBe(false)
    expect(accountActions(actor('owner'), target('admin'), NOW).actions).toMatchObject({
      changeStatus: true,
      changeRole: true,
    })
  })

  it('gives a regular user no actions', () => {
    expect(Object.values(accountActions(actor('user'), target('user'), NOW).actions)).not.toContain(true)
  })
})
