import { useQueryClient } from '@tanstack/react-query'
import { Info, RefreshCw, ShieldAlert, TriangleAlert, type LucideIcon } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { SeverityBadge } from '@/components/SeverityBadge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { SecurityEventType, Severity } from '@/features/account/api'
import type { AccountState, SecurityEvent, SecuritySummary } from '@/features/org/api'
import { DEFAULT_RANGE, type LogFilters, writeLogFilters } from '@/features/org/filters'
import {
  recentIncidentsKey,
  securitySummaryKey,
  useRecentIncidents,
  useSecuritySummary,
} from '@/features/org/hooks'
import { LogDetails } from '@/features/org/LogDetails'
import { LogTable } from '@/features/org/LogTable'
import { accountLabel, accountLinks, recordFields } from '@/features/org/records'
import { writeUserFilters } from '@/features/org/user-filters'
import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

/** The security event log, filtered; the defaults fill what is not given. */
function eventsLink(filters: Partial<LogFilters<SecurityEventType>>): string {
  const params = writeLogFilters({
    range: DEFAULT_RANGE,
    types: [],
    severities: [],
    search: '',
    ...filters,
  })
  return `/org/events?${params.toString()}`
}

function usersLink(state: AccountState): string {
  return `/org/users?${writeUserFilters({ search: '', roles: [], state }).toString()}`
}

export function OrgOverviewPage() {
  const { t } = useTranslation()
  const format = useFormatters()
  const queryClient = useQueryClient()
  const summary = useSecuritySummary()
  const incidents = useRecentIncidents()

  const refreshing = summary.isFetching || incidents.isFetching
  const refresh = () => {
    // Both together, so the counts and the incidents describe the same moment.
    void queryClient.invalidateQueries({ queryKey: securitySummaryKey })
    void queryClient.invalidateQueries({ queryKey: recentIncidentsKey })
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold">{t('orgOverview.title')}</h1>
          <p className="max-w-prose text-muted-foreground">{t('orgOverview.subtitle')}</p>
        </div>
        <div className="flex flex-col items-start gap-1 sm:items-end">
          <Button variant="outline" disabled={refreshing} onClick={refresh}>
            <RefreshCw aria-hidden className={cn(refreshing && 'animate-spin')} />
            {t('orgLog.refresh')}
          </Button>
          {summary.data && (
            <p className="text-xs text-muted-foreground">
              {t('orgOverview.updated')}{' '}
              <time dateTime={summary.data.generated_at} title={format.dateTime(summary.data.generated_at)}>
                {format.relative(summary.data.generated_at)}
              </time>
            </p>
          )}
        </div>
      </header>

      <SummaryTiles summary={summary} />

      <section aria-labelledby="recent-incidents" className="flex flex-col gap-3">
        <SectionHeading id="recent-incidents" help={t('orgOverview.incidentsHelp')}>
          {t('orgOverview.incidents')}
        </SectionHeading>
        <RecentIncidents query={incidents} />
      </section>

      <section aria-labelledby="failed-login-sources" className="flex flex-col gap-3">
        <SectionHeading id="failed-login-sources" help={t('orgOverview.sourcesHelp')}>
          {t('orgOverview.sources')}
        </SectionHeading>
        <FailedLoginSources summary={summary} />
      </section>
    </div>
  )
}

function SectionHeading({ id, help, children }: { id: string; help: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <h2 id={id} className="text-sm font-semibold">
        {children}
      </h2>
      <p className="text-sm text-muted-foreground">{help}</p>
    </div>
  )
}

interface SummaryQuery {
  data?: SecuritySummary
  isPending: boolean
  isError: boolean
  refetch: () => unknown
}

function LoadFailed({ onRetry }: { onRetry: () => unknown }) {
  const { t } = useTranslation()
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border px-4 py-4">
      <p className="text-muted-foreground">{t('errors.loadFailedBody')}</p>
      <Button variant="outline" size="sm" onClick={() => void onRetry()}>
        {t('errors.retry')}
      </Button>
    </div>
  )
}

const SEVERITY_TILES: { severity: Severity; icon: LucideIcon; iconClass: string }[] = [
  { severity: 'incident', icon: ShieldAlert, iconClass: 'text-sev-incident' },
  { severity: 'warn', icon: TriangleAlert, iconClass: 'text-sev-warn' },
  { severity: 'info', icon: Info, iconClass: 'text-sev-info' },
]

/** The headline counts. Each opens the records behind it. */
function SummaryTiles({ summary }: { summary: SummaryQuery }) {
  const { t } = useTranslation()
  const format = useFormatters()

  if (summary.isPending) {
    return (
      <div role="status" aria-label={t('app.loading')} className="grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-3">
        {Array.from({ length: 6 }, (_, index) => (
          <div key={index} className="flex flex-col gap-2 bg-card px-4 py-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-16" />
          </div>
        ))}
      </div>
    )
  }

  if (summary.isError || !summary.data) {
    return <LoadFailed onRetry={summary.refetch} />
  }

  const data = summary.data
  return (
    <ul
      aria-label={t('orgOverview.summaryLabel')}
      className="grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-3"
    >
      {SEVERITY_TILES.map(({ severity, icon, iconClass }) => (
        <Tile
          key={severity}
          to={eventsLink({ range: '24h', severities: [severity] })}
          label={t(`orgOverview.severity.${severity}`)}
          icon={icon}
          iconClass={iconClass}
          value={format.number(data.last_24h[severity])}
          unit={t('orgOverview.in24h')}
          detail={t('orgOverview.in7d', { value: format.number(data.last_7d[severity]) })}
        />
      ))}
      <Tile
        to={eventsLink({ range: '24h', types: ['login_failed'] })}
        label={t('orgOverview.failedLogins')}
        value={format.number(data.failed_logins_24h)}
        unit={t('orgOverview.in24h')}
        detail={t('orgOverview.lockedLogins', { count: data.locked_logins, value: format.number(data.locked_logins) })}
      />
      <Tile
        to={usersLink('locked')}
        label={t('orgOverview.accountsLocked')}
        value={format.number(data.accounts_locked)}
        detail={t('orgOverview.accountsLockedDetail')}
      />
      <Tile
        to={usersLink('inactive')}
        label={t('orgOverview.accountsInactive')}
        value={format.number(data.users_inactive)}
        detail={t('orgOverview.ofAccounts', { count: data.users_total, value: format.number(data.users_total) })}
      />
    </ul>
  )
}

interface TileProps {
  to: string
  label: string
  icon?: LucideIcon
  iconClass?: string
  value: string
  unit?: string
  detail: string
}

function Tile({ to, label, icon: Icon, iconClass, value, unit, detail }: TileProps) {
  return (
    <li className="flex">
      <Link
        to={to}
        className="flex w-full flex-col gap-1.5 bg-card px-4 py-4 transition-colors hover:bg-accent/40 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none focus-visible:ring-inset"
      >
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {Icon && <Icon aria-hidden className={cn('size-3.5', iconClass)} />}
          {label}
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="text-2xl font-semibold">{value}</span>
          {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
        </span>
        <span className="text-xs text-muted-foreground">{detail}</span>
      </Link>
    </li>
  )
}

interface IncidentsQuery {
  data?: { items: SecurityEvent[] }
  isPending: boolean
  isError: boolean
  refetch: () => unknown
}

function RecentIncidents({ query }: { query: IncidentsQuery }) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<SecurityEvent | null>(null)
  const describe = (event: SecurityEvent) => t(`orgEvents.types.${event.event_type}`)

  if (query.isPending) {
    return (
      <div role="status" aria-label={t('app.loading')} className="flex flex-col gap-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (query.isError || !query.data) {
    return <LoadFailed onRetry={query.refetch} />
  }

  const items = query.data.items
  return (
    <div className="flex flex-col items-start gap-3">
      {items.length === 0 ? (
        <p className="w-full rounded-lg border bg-card px-4 py-4 text-muted-foreground">
          {t('orgOverview.noIncidents')}
        </p>
      ) : (
        <LogTable
          label={t('orgOverview.incidents')}
          items={items}
          describe={describe}
          onSelect={setSelected}
          columns={[
            {
              header: t('orgLog.account'),
              cell: (event) => accountLabel(event, t),
              className: 'max-w-56 truncate font-mono text-xs',
            },
            {
              header: t('orgLog.ipAddress'),
              cell: (event) => event.ip_address ?? t('orgLog.none'),
              className: 'font-mono text-xs text-muted-foreground',
            },
          ]}
        />
      )}
      <Button asChild variant="outline" size="sm">
        <Link to={eventsLink({ severities: ['incident'] })}>{t('orgOverview.viewIncidents')}</Link>
      </Button>

      <LogDetails
        record={selected}
        onClose={() => setSelected(null)}
        title={selected ? describe(selected) : ''}
        badge={selected && <SeverityBadge severity={selected.severity} />}
        fields={
          selected
            ? [
                ...recordFields(selected, t),
                { label: t('orgLog.source'), value: selected.source, mono: true },
                { label: t('orgLog.message'), value: selected.message, mono: true },
              ]
            : []
        }
        actions={selected ? accountLinks(selected, t) : []}
      />
    </div>
  )
}

/** The addresses with the most failed sign-ins, as bars scaled to the
 * largest. The count is written beside each bar, so it never rests on
 * length alone. */
function FailedLoginSources({ summary }: { summary: SummaryQuery }) {
  const { t } = useTranslation()
  const format = useFormatters()

  if (summary.isPending) {
    return <Skeleton role="status" aria-label={t('app.loading')} className="h-24 w-full" />
  }

  if (summary.isError || !summary.data) {
    // The tiles above already offer the retry.
    return <p className="text-muted-foreground">{t('orgOverview.unavailable')}</p>
  }

  const sources = summary.data.top_failed_login_sources
  if (sources.length === 0) {
    return (
      <p className="rounded-lg border bg-card px-4 py-4 text-muted-foreground">
        {t('orgOverview.noSources')}
      </p>
    )
  }

  const largest = Math.max(...sources.map((source) => source.failed_logins))
  return (
    <ol aria-label={t('orgOverview.sources')} className="flex flex-col rounded-lg border bg-card">
      {sources.map((source) => (
        <li key={source.ip_address} className="border-b last:border-b-0">
          <Link
            to={eventsLink({ range: '24h', types: ['login_failed'], search: source.ip_address })}
            aria-label={t('orgOverview.sourceLabel', {
              ip: source.ip_address,
              count: source.failed_logins,
            })}
            className="grid grid-cols-[minmax(7rem,12rem)_1fr_auto] items-center gap-4 px-4 py-2.5 transition-colors hover:bg-accent/40 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none focus-visible:ring-inset"
          >
            <span className="truncate font-mono text-xs">{source.ip_address}</span>
            <span aria-hidden className="h-2">
              <span
                className="block h-full rounded-r-[4px] bg-brand"
                style={{ width: `${(source.failed_logins / largest) * 100}%` }}
              />
            </span>
            <span className="text-right font-mono text-xs tabular-nums text-muted-foreground">
              {format.number(source.failed_logins)}
            </span>
          </Link>
        </li>
      ))}
    </ol>
  )
}
