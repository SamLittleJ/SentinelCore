import { Search } from 'lucide-react'
import { Suspense, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation } from 'react-router'

import { Wordmark } from '@/components/brand/Logomark'
import { Skeleton } from '@/components/ui/skeleton'
import { canViewOrganization, type CurrentUser } from '@/features/auth/api'
import { useCurrentUser } from '@/features/auth/hooks'
import { useSecuritySummary } from '@/features/org/hooks'
import { OrganizationViewProvider } from '@/features/org/OrganizationViewProvider'
import { cn } from '@/lib/utils'

import { AccountMenu } from './AccountMenu'
import { CommandPalette } from './CommandPalette'
import { type NavItem, navItems, type Scope, scopeName, scopeOf } from './navigation'

/** The incidents of the last 24 hours, beside the events they are in. The
 * count comes from the summary, which is not audited. */
function IncidentBadge() {
  const { t } = useTranslation()
  const summary = useSecuritySummary()
  const count = summary.data?.last_24h.incident ?? 0
  if (count === 0) return null
  return (
    <span className="ml-auto shrink-0 text-xs font-semibold text-sev-incident tabular-nums">
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
          'flex shrink-0 items-center gap-3 rounded-md px-2.5 py-1.5 whitespace-nowrap transition-colors',
          isActive
            ? 'bg-sidebar-accent font-semibold text-sidebar-accent-foreground'
            : 'text-muted-foreground hover:bg-accent hover:text-sidebar-foreground',
        )
      }
    >
      <span className="min-w-0 truncate">{t(item.label)}</span>
      {badge && <IncidentBadge />}
    </NavLink>
  )
}

/** One group of pages: the organization's, or the user's own. The incident
 * count shows on organization pages only, so personal pages never load it. */
function NavGroup({ scope, user, heading }: { scope: Scope; user: CurrentUser; heading?: string }) {
  const { t } = useTranslation()
  const inOrganization = scopeOf(useLocation().pathname) === 'organization'
  return (
    // One scrolling row on a phone, a column beside the page from md up.
    <nav
      aria-label={heading ?? t('nav.label')}
      className="flex gap-0.5 overflow-x-auto [scrollbar-width:thin] md:flex-col md:overflow-visible"
    >
      {heading && (
        <p className="hidden truncate px-2.5 pb-1 text-xs font-medium text-muted-foreground md:block">{heading}</p>
      )}
      {navItems(scope, user).map((item) => (
        <NavEntry key={item.to} item={item} badge={inOrganization && item.label === 'nav.securityEvents'} />
      ))}
    </nav>
  )
}

function Sidebar({ user, onOpenPalette }: { user: CurrentUser; onOpenPalette: () => void }) {
  const { t } = useTranslation()
  const operator = canViewOrganization(user)

  return (
    <aside className="flex shrink-0 flex-col gap-5 border-b border-sidebar-border bg-sidebar p-3 text-sidebar-foreground md:sticky md:top-0 md:h-screen md:w-64 md:border-r md:border-b-0">
      <div className="px-1.5 pt-1">
        <Wordmark />
      </div>

      <button
        type="button"
        onClick={onOpenPalette}
        aria-keyshortcuts="Control+K Meta+K"
        className="flex h-9 items-center gap-2 rounded-md border border-input bg-background px-2.5 text-muted-foreground transition-colors hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none"
      >
        <Search aria-hidden className="size-4" />
        <span className="min-w-0 truncate">{t('palette.open')}</span>
        <kbd className="ml-auto shrink-0 rounded border border-input px-1.5 text-xs whitespace-nowrap">Ctrl K</kbd>
      </button>

      <div className="flex flex-col gap-1 md:gap-6">
        {operator && <NavGroup scope="organization" user={user} heading={scopeName('organization', user, t)} />}
        <NavGroup scope="personal" user={user} heading={operator ? scopeName('personal', user, t) : undefined} />
      </div>

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
    <OrganizationViewProvider enabled={user.role === 'owner'}>
      <div className="flex min-h-screen flex-col md:flex-row">
        <Sidebar user={user} onOpenPalette={() => setPaletteOpen(true)} />
        <main className="min-w-0 flex-1">
          <div className="px-4 pt-6 pb-12 md:px-8">
            {/* One left-aligned column for every page, so titles keep their
                place between pages and dense tables fit on one line. */}
            <div className="w-full max-w-[75rem]">
              <Suspense fallback={<PageLoader />}>
                <Outlet />
              </Suspense>
            </div>
          </div>
        </main>
        <CommandPalette user={user} open={paletteOpen} onOpenChange={setPaletteOpen} />
      </div>
    </OrganizationViewProvider>
  )
}
