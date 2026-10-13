// The application's pages, shared by the sidebar, the page headers and the
// command palette, so their names and numbers always agree.

import type { TFunction } from 'i18next'

import type { CurrentUser, User } from '@/features/auth/api'

export type Scope = 'personal' | 'organization'

export type NavKey =
  | 'nav.overview'
  | 'nav.mySessions'
  | 'nav.myActivity'
  | 'nav.securityEvents'
  | 'nav.auditLog'
  | 'nav.users'
  | 'nav.apiKeys'
  | 'nav.organizations'

export interface NavItem {
  to: string
  label: NavKey
  // Shown before the name, as in a console: "01", "02"…
  number: string
  // Matches only the exact path, not the pages below it.
  end?: boolean
  // Shown to the platform owner only, as the API allows only them.
  ownerOnly?: boolean
}

function numbered(items: Omit<NavItem, 'number'>[]): NavItem[] {
  return items.map((item, index) => ({ ...item, number: String(index + 1).padStart(2, '0') }))
}

export const NAV: Record<Scope, NavItem[]> = {
  personal: numbered([
    { to: '/me', label: 'nav.overview', end: true },
    { to: '/me/sessions', label: 'nav.mySessions' },
    { to: '/me/activity', label: 'nav.myActivity' },
  ]),
  organization: numbered([
    { to: '/org', label: 'nav.overview', end: true },
    { to: '/org/events', label: 'nav.securityEvents' },
    { to: '/org/audit', label: 'nav.auditLog' },
    { to: '/org/users', label: 'nav.users' },
    { to: '/org/api-keys', label: 'nav.apiKeys' },
    // Last, so the pages before it keep their numbers for everyone.
    { to: '/org/organizations', label: 'nav.organizations', ownerOnly: true },
  ]),
}

/** The pages of `scope` that `user` may open. */
export function navItems(scope: Scope, user: User): NavItem[] {
  return NAV[scope].filter((item) => !item.ownerOnly || user.role === 'owner')
}

/** What the scope is called for `user`: the platform for its owner, the
 * name of their organization for everyone else. */
export function scopeName(scope: Scope, user: CurrentUser | undefined, t: TFunction): string {
  if (scope === 'personal') return t('scope.personal')
  if (user?.role === 'owner') return t('scope.platform')
  return user?.organization?.name ?? t('scope.organization')
}

export function scopeOf(pathname: string): Scope {
  return pathname === '/org' || pathname.startsWith('/org/') ? 'organization' : 'personal'
}

/** The page `pathname` belongs to: itself, or the closest page above it
 * (an account's page belongs to Users). */
export function navItemFor(pathname: string): NavItem | undefined {
  const items = NAV[scopeOf(pathname)]
  return (
    items.find((item) => item.to === pathname) ??
    items
      .filter((item) => !item.end && pathname.startsWith(`${item.to}/`))
      .sort((a, b) => b.to.length - a.to.length)[0]
  )
}
