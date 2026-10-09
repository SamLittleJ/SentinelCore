import { Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation } from 'react-router'

import { Skeleton } from '@/components/ui/skeleton'
import { canViewOrganization, type User } from '@/features/auth/api'
import { useCurrentUser } from '@/features/auth/hooks'
import { cn } from '@/lib/utils'

import { AccountMenu } from './AccountMenu'

type NavKey =
  | 'nav.overview'
  | 'nav.mySessions'
  | 'nav.myActivity'
  | 'nav.securityEvents'
  | 'nav.auditLog'
  | 'nav.users'
  | 'nav.apiKeys'

const PERSONAL_NAV: { to: string; label: NavKey; end?: boolean }[] = [
  { to: '/me', label: 'nav.overview', end: true },
  { to: '/me/sessions', label: 'nav.mySessions' },
  { to: '/me/activity', label: 'nav.myActivity' },
]

const ORGANIZATION_NAV: { to: string; label: NavKey; end?: boolean }[] = [
  { to: '/org', label: 'nav.overview', end: true },
  { to: '/org/events', label: 'nav.securityEvents' },
  { to: '/org/audit', label: 'nav.auditLog' },
  { to: '/org/users', label: 'nav.users' },
  { to: '/org/api-keys', label: 'nav.apiKeys' },
]

function BrandMark() {
  return (
    <span
      aria-hidden
      className="grid size-7 place-items-center rounded-md bg-sidebar-primary font-mono text-xs font-semibold text-sidebar-primary-foreground"
    >
      SC
    </span>
  )
}

function ScopeSwitch({ inOrganization }: { inOrganization: boolean }) {
  const { t } = useTranslation()
  const option = (active: boolean) =>
    cn(
      'rounded-[5px] px-2 py-1.5 text-center text-xs transition-colors',
      active
        ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
        : 'text-muted-foreground hover:text-sidebar-foreground',
    )

  return (
    <nav aria-label={t('scope.label')} className="grid grid-cols-2 gap-1 rounded-lg border border-sidebar-border bg-background/40 p-1">
      <NavLink to="/me" className={option(!inOrganization)} aria-current={!inOrganization ? 'page' : undefined}>
        {t('scope.personal')}
      </NavLink>
      <NavLink to="/org" className={option(inOrganization)} aria-current={inOrganization ? 'page' : undefined}>
        {t('scope.organization')}
      </NavLink>
    </nav>
  )
}

function Sidebar({ user }: { user: User }) {
  const { t } = useTranslation()
  const location = useLocation()
  const inOrganization = location.pathname === '/org' || location.pathname.startsWith('/org/')
  const items = inOrganization ? ORGANIZATION_NAV : PERSONAL_NAV

  return (
    <aside className="flex shrink-0 flex-col gap-5 border-b border-sidebar-border bg-sidebar p-3 text-sidebar-foreground md:sticky md:top-0 md:h-screen md:w-60 md:border-r md:border-b-0">
      <div className="flex items-center gap-2.5 px-2 pt-1 font-semibold tracking-tight">
        <BrandMark />
        {t('app.name')}
      </div>

      {canViewOrganization(user) && <ScopeSwitch inOrganization={inOrganization} />}

      <nav aria-label={t('nav.label')} className="flex gap-1 overflow-x-auto [scrollbar-width:thin] md:flex-col">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                'shrink-0 rounded-md px-2.5 py-1.5 whitespace-nowrap transition-colors',
                isActive
                  ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
                  : 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
              )
            }
          >
            {t(item.label)}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto border-t border-sidebar-border pt-2">
        <AccountMenu user={user} />
      </div>
    </aside>
  )
}

/** Shown while a page loaded on demand arrives. */
function PageLoader() {
  const { t } = useTranslation()
  return (
    <div role="status" aria-label={t('app.loading')} className="flex flex-col gap-4">
      <Skeleton className="h-7 w-56" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  )
}

export function AppShell() {
  const { data: user } = useCurrentUser()

  // RequireAuth renders this only once the user is loaded.
  if (user === undefined) {
    return null
  }

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar user={user} />
      <main className="min-w-0 flex-1 px-4 pt-8 pb-12 md:px-8 md:pt-12">
        {/* One centered column for every page, so titles keep their place
            when moving between pages and wide screens stay balanced. */}
        <div className="mx-auto w-full max-w-5xl">
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  )
}
