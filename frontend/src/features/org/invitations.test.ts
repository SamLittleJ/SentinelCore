import { describe, expect, it } from 'vitest'

import { canRevokeInvitation, invitableRoles, invitationState } from '@/features/org/invitations'
import { makeInvitation, makeUser } from '@/test/server'

const NOW = Date.parse('2026-10-11T12:00:00Z')
const LATER = '2026-10-12T12:00:00Z'
const EARLIER = '2026-10-10T12:00:00Z'

describe('invitationState', () => {
  it('is open until it expires', () => {
    expect(invitationState(makeInvitation({ expires_at: LATER }), NOW)).toBe('open')
    expect(invitationState(makeInvitation({ expires_at: EARLIER }), NOW)).toBe('expired')
  })

  it('stays accepted or revoked whatever its expiry', () => {
    expect(
      invitationState(makeInvitation({ expires_at: EARLIER, accepted_at: EARLIER }), NOW),
    ).toBe('accepted')
    expect(invitationState(makeInvitation({ expires_at: EARLIER, revoked_at: EARLIER }), NOW)).toBe(
      'revoked',
    )
  })
})

describe('invitableRoles', () => {
  it('lets an admin offer everyday roles and the owner an admin role too', () => {
    expect(invitableRoles(makeUser('admin'))).toEqual(['user', 'security_analyst'])
    expect(invitableRoles(makeUser('owner'))).toEqual(['user', 'security_analyst', 'admin'])
  })

  it('offers nothing to readers or to a deactivated admin', () => {
    expect(invitableRoles(makeUser('security_analyst'))).toEqual([])
    expect(invitableRoles(makeUser('user'))).toEqual([])
    expect(invitableRoles(makeUser('admin', { is_active: false }))).toEqual([])
  })
})

describe('canRevokeInvitation', () => {
  const open = { expires_at: LATER }

  it('follows who may offer the role', () => {
    const adminInvite = makeInvitation({ ...open, role: 'admin' })
    expect(canRevokeInvitation(makeUser('admin'), adminInvite, NOW)).toBe(false)
    expect(canRevokeInvitation(makeUser('owner'), adminInvite, NOW)).toBe(true)
    expect(canRevokeInvitation(makeUser('admin'), makeInvitation({ ...open }), NOW)).toBe(true)
    expect(canRevokeInvitation(makeUser('security_analyst'), makeInvitation(open), NOW)).toBe(false)
  })

  it('only applies to open invitations', () => {
    const owner = makeUser('owner')
    expect(canRevokeInvitation(owner, makeInvitation({ expires_at: EARLIER }), NOW)).toBe(false)
    expect(canRevokeInvitation(owner, makeInvitation({ ...open, accepted_at: EARLIER }), NOW)).toBe(
      false,
    )
  })
})
