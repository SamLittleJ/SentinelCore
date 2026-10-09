import { Search } from 'lucide-react'
import { Suspense, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation } from 'react-router'

import { Wordmark } from '@/components/brand/Logomark'
import { Skeleton } from '@/components/ui/skeleton'
import { canViewOrganization, type User } from '@/features/auth/api'
import { useCurrentUser } from '@/features/auth/hooks'
import { useSecuritySummary } from '@/features/org/hooks'
import { cn } from '@/lib/utils'

import { AccountMenu } from './AccountMenu'
import { CommandPalette } from './CommandPalette'
import { NAV, type NavItem, scopeOf } from './navigation'

function ScopeSwitch({ inOrganization }: { inOrganization: boolean }) {
  const { t } = useTranslation()
  const option = (active: boolean) =>
    cn(
      'label-mono -mb-px border-b-2 px-2 py-2 text-center transition-colors',
      active
        ? 'border-brand text-brand'
        : 'border-transparent text-muted-foreground hover:text-sidebar-foreground',
    )

  return (
    <nav aria-label={t('scope.label')} className="grid grid-cols-2 border-b border-sidebar-border">
      <NavLink to="/me" className={option(!inOrganization)} aria-current={!inOrganization ? 'page' : undefined}>
        {t('scope.personal')}
      </NavLink>
      <NavLink to="/org" className={option(inOrganization)} aria-current={inOrganization ? 'page' : undefined}>
        {t('scope.organization')}
      </NavLink>
    </nav>
  )
}

/** The incidents of the last 24 hours, beside the events they are in. The
 * count comes from the summary, which is not audited. */
function IncidentBadge() {
  const { t } = useTranslation()
  const summary = useSecuritySummary()
  const count = summary.data?.last_24h.incident ?? 0
  if (count === 0) return null
  return (
    <span className="ml-auto shrink-0 rounded-full bg-sev-incident-bg px-1.5 font-mono text-[11px] text-sev-incident">
      <span aria-hidden>{count}</span>
      <span className="sr-only">{t('nav.incidentsBadge', { count })}</span>
    </span>
  )
}

function NavEntry({ item, badge }: { item: NavItem; badge?: boolean }) {
  const { t } = useTranslation()
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        cn(
          'group flex shrink-0 items-center gap-3 rounded-md px-2.5 py-2 whitespace-nowrap transition-colors',
          isActive
            ? 'bg-sidebar-accent/70 font-medium text-sidebar-foreground'
            : 'text-muted-foreground hover:bg-sidebar-accent/40 hover:text-sidebar-foreground',
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            aria-hidden
            className={cn('font-mono text-[11px]', isActive ? 'text-brand' : 'text-muted-foreground/60')}
          >
            {item.number}
          </span>
          <span className="min-w-0 truncate">{t(item.label)}</span>
          {badge && <IncidentBadge />}
        </>
      )}
    </NavLink>
  )
}

function Sidebar({ user, onOpenPalette }: { user: User; onOpenPalette: () => void }) {
  const { t } = useTranslation()
  const location = useLocation()
  const scope = scopeOf(location.pathname)
  const inOrganization = scope === 'organization'

  return (
    <aside className="flex shrink-0 flex-col gap-5 border-b border-sidebar-border bg-sidebar p-4 text-sidebar-foreground md:sticky md:top-0 md:h-screen md:w-72 md:border-r md:border-b-0">
      <div className="flex items-center justify-between gap-2 px-1 pt-1">
        <Wordmark />
      </div>

      <button
        type="button"
        onClick={onOpenPalette}
        aria-keyshortcuts="Control+K Meta+K"
        className="flex h-10 items-center gap-2 rounded-md border border-sidebar-border bg-background/40 px-3 text-muted-foreground transition-colors hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none"
      >
        <Search aria-hidden className="size-4" />
        <span className="min-w-0 truncate">{t('palette.open')}</span>
        <kbd className="label-mono ml-auto shrink-0 rounded border border-sidebar-border px-1.5 tracking-normal whitespace-nowrap normal-case">
          Ctrl K
        </kbd>
      </button>

      {canViewOrganization(user) && <ScopeSwitch inOrganization={inOrganization} />}

      <nav aria-label={t('nav.label')} className="flex gap-1 overflow-x-auto [scrollbar-width:thin] md:flex-col md:overflow-visible">
        {NAV[scope].map((item) => (
          <NavEntry key={item.to} item={item} badge={inOrganization && item.label === 'nav.securityEvents'} />
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
  const [paletteOpen, setPaletteOpen] = useState(false)

  // Ctrl+K, or Cmd+K on a Mac, from anywhere in the application.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  // RequireAuth renders this only once the user is loaded.
  if (user === undefined) {
    return null
  }

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar user={user} onOpenPalette={() => setPaletteOpen(true)} />
      <main className="min-w-0 flex-1 px-4 pt-8 pb-12 md:px-8 md:pt-12">
        {/* One centered column for every page, so titles keep their place
            when moving between pages and wide screens stay balanced. */}
        <div className="mx-auto w-full max-w-5xl">
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
      <CommandPalette user={user} open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  )
}
