import type { Role, User } from '@/features/auth/api'

/** Whether an operator's lock is in force at `now`. */
export function isLockedNow(user: User, now = Date.now()): boolean {
  return user.locked_until !== null && Date.parse(user.locked_until) > now
}

export interface AccountActions {
  revokeSessions: boolean
  lock: boolean
  unlock: boolean
  changeStatus: boolean
  changeRole: boolean
}

// Why an account offers no actions at all.
export type ActionRestriction = 'self' | 'owner'

const CONTAINMENT_ROLES: ReadonlySet<Role> = new Set(['admin', 'owner', 'security_analyst'])
const MANAGEMENT_ROLES: ReadonlySet<Role> = new Set(['admin', 'owner'])

/**
 * The actions `actor` may take on `target`, mirroring the API's rules so the
 * page only offers what would be allowed. The API still decides.
 */
export function accountActions(
  actor: User,
  target: User,
  now = Date.now(),
): { actions: AccountActions; restriction?: ActionRestriction } {
  const none: AccountActions = {
    revokeSessions: false,
    lock: false,
    unlock: false,
    changeStatus: false,
    changeRole: false,
  }
  // Nobody acts on their own account or on an owner.
  if (actor.id === target.id) return { actions: none, restriction: 'self' }
  if (target.role === 'owner') return { actions: none, restriction: 'owner' }

  // Containment is reversible, so any operator may contain an admin; lifting
  // a lock early is reviewed by an admin or the owner.
  const contains = CONTAINMENT_ROLES.has(actor.role)
  const manages = MANAGEMENT_ROLES.has(actor.role)
  return {
    actions: {
      revokeSessions: contains,
      lock: contains,
      unlock: manages && isLockedNow(target, now),
      // Only the owner changes an admin's status.
      changeStatus: manages && !(actor.role === 'admin' && target.role === 'admin'),
      changeRole: actor.role === 'owner',
    },
  }
}
