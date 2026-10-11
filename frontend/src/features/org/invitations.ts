import type { Role, User } from '@/features/auth/api'

import type { AssignableRole, Invitation } from './api'

export type InvitationState = 'open' | 'accepted' | 'revoked' | 'expired'

/** Whether `invitation` can still be accepted at `now`, as the API decides
 * it: a used or revoked invitation stays so, whatever its expiry. */
export function invitationState(invitation: Invitation, now = Date.now()): InvitationState {
  if (invitation.accepted_at !== null) return 'accepted'
  if (invitation.revoked_at !== null) return 'revoked'
  return Date.parse(invitation.expires_at) > now ? 'open' : 'expired'
}

// Admins grow the organization with everyday roles; only the owner adds
// another admin. Mirrors the API's rule, which still decides.
const INVITABLE_ROLES: Partial<Record<Role, readonly AssignableRole[]>> = {
  admin: ['user', 'security_analyst'],
  owner: ['user', 'security_analyst', 'admin'],
}

/** The roles `actor` may offer, none for those who only read the list. */
export function invitableRoles(actor: User): readonly AssignableRole[] {
  return actor.is_active ? (INVITABLE_ROLES[actor.role] ?? []) : []
}

/** Whoever may offer a role may also withdraw an invitation for it. */
export function canRevokeInvitation(actor: User, invitation: Invitation, now = Date.now()) {
  return (
    invitationState(invitation, now) === 'open' &&
    (invitableRoles(actor) as readonly Role[]).includes(invitation.role)
  )
}
