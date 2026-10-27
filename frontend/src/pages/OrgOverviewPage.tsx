import { useQueryClient } from '@tanstack/react-query'
import { Info, RefreshCw, ShieldAlert, TriangleAlert, type LucideIcon } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { LoadFailed } from '@/components/LoadFailed'
import { SeverityBadge } from '@/components/SeverityBadge'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { SecurityEventType, Severity } from '@/features/account/api'
import type {
  AccountState,
  OrganizationLevel,
  SecurityEvent,
  SecuritySummary,
  SeverityCounts,
  ThreatLevel,
} from '@/features/org/api'
import { DEFAULT_RANGE, type LogFilters, writeLogFilters } from '@/features/org/filters'
import {
  recentIncidentsKey,
  securitySummaryKey,
  useRecentIncidents,
  useSecuritySummary,
} from '@/features/org/hooks'
import { LogDetails } from '@/features/org/LogDetails'
import { accountLabel, accountLinks } from '@/features/org/records'
import { techniqueName } from '@/features/org/mitre'
import { useOrganizationView } from '@/features/org/organization-view'
import { securityEventFields, techniqueBadge } from '@/features/org/security-event-fields'
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
  // Only the owner's summary of the whole platform lists organizations.
  const levels = summary.data?.organizations ?? null
  const refreshing = summary.isFetching || incidents.isFetching
  const refresh = () => {
    // Both together, so the counts and the incidents describe the same moment.
    void queryClient.invalidateQueries({ queryKey: securitySummaryKey })
    void queryClient.invalidateQueries({ queryKey: recentIncidentsKey })
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={levels ? t('orgOverview.platformTitle') : t('orgOverview.title')}
        actions={
          <div className="flex items-center gap-3">
            {summary.data && (
              <p className="text-sm text-muted-foreground">
                {t('orgOverview.updated')}{' '}
                <time dateTime={summary.data.generated_at} title={format.dateTime(summary.data.generated_at)}>
                  {format.relative(summary.data.generated_at)}
                </time>
              </p>
            )}
            <Button variant="outline" disabled={refreshing} onClick={refresh}>
              <RefreshCw aria-hidden className={cn(refreshing && 'animate-spin')} />
              {t('orgLog.refresh')}
            </Button>
          </div>
        }
      />

      <ThreatStatus summary={summary} />

      <section aria-labelledby="recent-incidents" className="flex flex-col gap-3">
        <SectionHeading id="recent-incidents" help={t('orgOverview.incidentsHelp')}>
          {t('orgOverview.incidents')}
        </SectionHeading>
        <RecentIncidents query={incidents} />
      </section>

      <SummaryStrip summary={summary} />

      <HourlyChart summary={summary} />

      <div className="grid gap-8 lg:grid-cols-2">
        {levels && (
          <section aria-labelledby="organizations-by-level" className="flex flex-col gap-3">
            <SectionHeading id="organizations-by-level" help={t('orgOverview.byLevelHelp')}>
              {t('orgOverview.byLevel')}
            </SectionHeading>
            <OrganizationsByLevel levels={levels} />
          </section>
        )}

        <section aria-labelledby="detected-techniques" className="flex flex-col gap-3">
          <SectionHeading id="detected-techniques" help={t('orgOverview.techniquesHelp')}>
            {t('orgOverview.techniques')}
          </SectionHeading>
          <DetectedTechniques summary={summary} />
        </section>

        <section aria-labelledby="failed-login-sources" className="flex flex-col gap-3">
          <SectionHeading id="failed-login-sources" help={t('orgOverview.sourcesHelp')}>
            {t('orgOverview.sources')}
          </SectionHeading>
          <FailedLoginSources summary={summary} />
        </section>
      </div>
    </div>
  )
}

function SectionHeading({ id, help, children }: { id: string; help: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
      <h2 id={id} className="text-base font-semibold">
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

/** The organization's level and its latest detection, first thing on the
 * page. Counts only, from the summary, which is not audited; the link opens
 * the event log, which is. */
function ThreatStatus({ summary }: { summary: SummaryQuery }) {
  const { t } = useTranslation()
  const format = useFormatters()

  // The numbers below show the loading state and the retry.
  if (!summary.data) return null
  const data = summary.data
  const level = data.threat_level
  const latest = data.latest_detection
  const latestTypes =
    latest && data.techniques_7d.find((entry) => entry.technique === latest.technique)?.event_types

  return (
    <section aria-label={t('band.label')} className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {/* The level is written out, never shown by color alone. */}
      <p className={cn('flex items-center gap-2 text-lg font-semibold', LEVEL_TEXT[level])}>
        <span aria-hidden className={cn('size-2.5 rounded-full', LEVEL_DOTS[level])} />
        {t(`band.levels.${level}`)}
      </p>
      <p className="text-muted-foreground">
        {latest ? (
          <>
            {t('band.latest')}{' '}
            <Link
              to={eventsLink({ range: '24h', types: latestTypes ?? [] })}
              className="text-foreground underline-offset-4 hover:underline"
            >
              {latest.technique} {techniqueName(latest.technique)}
            </Link>
            {', '}
            <time dateTime={latest.created_at} title={format.dateTime(latest.created_at)}>
              {format.time(latest.created_at)}
            </time>
          </>
        ) : (
          t('band.noDetection')
        )}
      </p>
    </section>
  )
}

const SEVERITY_ICONS: { severity: Severity; icon: LucideIcon; iconClass: string }[] = [
  { severity: 'incident', icon: ShieldAlert, iconClass: 'text-sev-incident' },
  { severity: 'warn', icon: TriangleAlert, iconClass: 'text-sev-warn' },
  { severity: 'info', icon: Info, iconClass: 'text-sev-info' },
]

/** The headline counts in one ruled row. Each opens the records behind it. */
function SummaryStrip({ summary }: { summary: SummaryQuery }) {
  const { t } = useTranslation()
  const format = useFormatters()
  const grid = 'grid grid-cols-2 gap-px border-y bg-border sm:grid-cols-3 xl:grid-cols-6'

  if (summary.isPending) {
    return (
      <div role="status" aria-label={t('app.loading')} className={grid}>
        {Array.from({ length: 6 }, (_, index) => (
          <div key={index} className="flex flex-col gap-2 bg-background px-4 py-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-7 w-14" />
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
    <ul aria-label={t('orgOverview.summaryLabel')} className={grid}>
      {SEVERITY_ICONS.map(({ severity, icon, iconClass }) => (
        <Stat
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
      <Stat
        to={eventsLink({ range: '24h', types: ['login_failed'] })}
        label={t('orgOverview.failedLogins')}
        value={format.number(data.failed_logins_24h)}
        unit={t('orgOverview.in24h')}
        detail={t('orgOverview.lockedLogins', { count: data.locked_logins, value: format.number(data.locked_logins) })}
      />
      <Stat
        to={usersLink('locked')}
        label={t('orgOverview.accountsLocked')}
        value={format.number(data.accounts_locked)}
        detail={t('orgOverview.accountsLockedDetail')}
      />
      <Stat
        to={usersLink('inactive')}
        label={t('orgOverview.accountsInactive')}
        value={format.number(data.users_inactive)}
        detail={t('orgOverview.ofAccounts', { count: data.users_total, value: format.number(data.users_total) })}
      />
    </ul>
  )
}

interface StatProps {
  to: string
  label: string
  icon?: LucideIcon
  iconClass?: string
  value: string
  unit?: string
  detail: string
}

function Stat({ to, label, icon: Icon, iconClass, value, unit, detail }: StatProps) {
  return (
    <li className="flex">
      <Link
        to={to}
        className="flex w-full flex-col gap-0.5 bg-background px-4 py-3 transition-colors hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none focus-visible:ring-inset"
      >
        <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
          {Icon && <Icon aria-hidden className={cn('size-3.5', iconClass)} />}
          {label}
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="text-2xl font-semibold tabular-nums">{value}</span>
          {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
        </span>
        <span className="text-xs text-muted-foreground">{detail}</span>
      </Link>
    </li>
  )
}

const BAR_STYLES: Record<Severity, string> = {
  info: 'bg-sev-info/45',
  warn: 'bg-sev-warn',
  incident: 'bg-sev-incident',
}

/** The last 24 hours, hour by hour, each hour's events stacked by severity
 * and scaled to the busiest hour. The totals are read out once; the bars
 * are for the eye. */
function HourlyChart({ summary }: { summary: SummaryQuery }) {
  const { t } = useTranslation()
  const format = useFormatters()

  if (!summary.data) return null
  const { hourly, last_24h: totals } = summary.data
  const total = (counts: SeverityCounts) => counts.info + counts.warn + counts.incident
  const largest = Math.max(1, ...hourly.map((bucket) => total(bucket.counts)))

  return (
    <section aria-labelledby="events-per-hour" className="flex flex-col gap-3">
      <SectionHeading id="events-per-hour" help={t('orgOverview.perHourHelp')}>
        {t('orgOverview.perHour')}
      </SectionHeading>
      <p className="sr-only">
        {t('band.totals', { incident: totals.incident, warn: totals.warn, info: totals.info })}
      </p>
      <div aria-hidden className="flex flex-col gap-1.5">
        <div className="flex gap-4 text-xs text-muted-foreground">
          {(['incident', 'warn', 'info'] as const).map((severity) => (
            <span key={severity} className="flex items-center gap-1.5">
              <span className={cn('size-2.5 rounded-[2px]', BAR_STYLES[severity])} />
              {t(`severity.${severity}`)}
            </span>
          ))}
        </div>
        <div className="flex h-36 items-end gap-[3px] border-b">
          {hourly.map((bucket) => (
            <div
              key={bucket.start}
              title={t('band.hour', {
                time: format.time(bucket.start),
                incident: bucket.counts.incident,
                warn: bucket.counts.warn,
                info: bucket.counts.info,
              })}
              className="flex h-full flex-1 flex-col-reverse"
            >
              {(['info', 'warn', 'incident'] as const).map((severity) => (
                <span
                  key={severity}
                  className={BAR_STYLES[severity]}
                  style={{ height: `${(bucket.counts[severity] / largest) * 100}%` }}
                />
              ))}
            </div>
          ))}
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{t('band.dayAgo')}</span>
          <span>{t('band.now')}</span>
        </div>
      </div>
    </section>
  )
}

interface IncidentsQuery {
  data?: { items: SecurityEvent[] }
  isPending: boolean
  isError: boolean
  refetch: () => unknown
}

/** The newest incidents, the first thing an operator acts on. Open shows a
 * record's details, which records the read in the audit log. */
function RecentIncidents({ query }: { query: IncidentsQuery }) {
  const { t } = useTranslation()
  const format = useFormatters()
  const [selected, setSelected] = useState<SecurityEvent | null>(null)
  const describe = (event: SecurityEvent) => t(`orgEvents.types.${event.event_type}`)

  if (query.isPending) {
    return (
      <div role="status" aria-label={t('app.loading')} className="flex flex-col gap-2">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
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
        <p className="w-full rounded-md border px-4 py-3 text-muted-foreground">{t('orgOverview.noIncidents')}</p>
      ) : (
        <ol aria-label={t('orgOverview.incidents')} className="w-full divide-y overflow-hidden rounded-md border">
          {items.map((event) => (
            <li
              key={event.id}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 border-l-[3px] border-l-sev-incident py-3 pr-3 pl-4 sm:grid-cols-[minmax(0,1fr)_auto_auto]"
            >
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="flex flex-wrap items-center gap-2 font-medium">
                  {describe(event)}
                  {techniqueBadge(event)}
                </span>
                <span className="flex max-w-full gap-3 truncate font-mono text-xs text-muted-foreground">
                  <span>{accountLabel(event, t)}</span>
                  <span>{event.ip_address ?? t('orgLog.none')}</span>
                </span>
              </div>
              <time
                dateTime={event.created_at}
                title={format.dateTime(event.created_at)}
                className="hidden text-sm whitespace-nowrap text-muted-foreground sm:block"
              >
                {format.relative(event.created_at)}
              </time>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelected(event)}
                aria-label={t('orgOverview.openIncident', { name: describe(event) })}
              >
                {t('orgOverview.open')}
              </Button>
            </li>
          ))}
        </ol>
      )}
      <Button asChild variant="link" size="sm" className="px-0">
        <Link to={eventsLink({ severities: ['incident'] })}>{t('orgOverview.viewIncidents')}</Link>
      </Button>

      <LogDetails
        record={selected}
        onClose={() => setSelected(null)}
        title={selected ? describe(selected) : ''}
        badge={selected && <SeverityBadge severity={selected.severity} />}
        fields={selected ? securityEventFields(selected, t, format) : []}
        actions={selected ? accountLinks(selected, t) : []}
      />
    </div>
  )
}

const LEVEL_DOTS: Record<ThreatLevel, string> = {
  calm: 'bg-sev-ok',
  warn: 'bg-sev-warn',
  incident: 'bg-sev-incident',
}

const LEVEL_TEXT: Record<ThreatLevel, string> = {
  calm: 'text-sev-ok',
  warn: 'text-sev-warn',
  incident: 'text-sev-incident',
}

/** Every organization and the platform at their level, the worst first.
 * Picking one shows only its data on every page. Counts only, from the
 * summary, so nothing here is audited. */
function OrganizationsByLevel({ levels }: { levels: OrganizationLevel[] }) {
  const { t } = useTranslation()
  const format = useFormatters()
  const { choose } = useOrganizationView()

  return (
    <div className="w-full overflow-x-auto rounded-md border">
      <table aria-label={t('orgOverview.byLevel')} className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('organizations.organization')}
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('orgOverview.level')}
            </th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">
              {t('orgOverview.incidents24h')}
            </th>
            <th scope="col" className="hidden px-4 py-2.5 text-right font-medium sm:table-cell">
              {t('orgOverview.warnings24h')}
            </th>
          </tr>
        </thead>
        <tbody>
          {levels.map((level) => (
            <tr key={level.id ?? 'platform'} className="border-b last:border-b-0">
              <td className="min-w-40 px-4 py-2.5">
                <span className="flex flex-wrap items-center gap-2">
                  {level.id === null ? (
                    <span className="text-muted-foreground">{t('organizations.platform')}</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => choose(level.id)}
                      aria-label={t('orgOverview.show', { name: level.name })}
                      className="rounded-sm text-left font-medium hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                    >
                      {level.name}
                    </button>
                  )}
                  {level.suspended && (
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {t('organizations.states.suspended')}
                    </span>
                  )}
                </span>
              </td>
              <td className="px-4 py-2.5 whitespace-nowrap">
                {/* The level is written out, never shown by color alone. */}
                <span className="flex items-center gap-2">
                  <span aria-hidden className={cn('size-2 rounded-full', LEVEL_DOTS[level.threat_level])} />
                  <span className={LEVEL_TEXT[level.threat_level]}>
                    {t(`band.levels.${level.threat_level}`)}
                  </span>
                </span>
              </td>
              <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums">
                {format.number(level.last_24h.incident)}
              </td>
              <td className="hidden px-4 py-2.5 text-right font-mono text-xs tabular-nums sm:table-cell">
                {format.number(level.last_24h.warn)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Alerts per MITRE ATT&CK technique over 7 days, as bars scaled to the
 * most frequent, each opening the alerts behind it. */
function DetectedTechniques({ summary }: { summary: SummaryQuery }) {
  const { t } = useTranslation()
  const format = useFormatters()

  if (summary.isPending) {
    return <Skeleton role="status" aria-label={t('app.loading')} className="h-24 w-full" />
  }
  if (summary.isError || !summary.data) {
    return <p className="text-muted-foreground">{t('orgOverview.unavailable')}</p>
  }

  const techniques = summary.data.techniques_7d
  if (techniques.length === 0) {
    return (
      <p className="rounded-md border px-4 py-4 text-muted-foreground">
        {t('orgOverview.noTechniques')}
      </p>
    )
  }

  const largest = Math.max(...techniques.map((entry) => entry.alerts))
  return (
    <ol aria-label={t('orgOverview.techniques')} className="flex flex-col rounded-md border">
      {techniques.map((entry) => (
        <li key={entry.technique} className="border-b last:border-b-0">
          <Link
            to={eventsLink({ types: entry.event_types })}
            aria-label={t('orgOverview.techniqueLabel', {
              technique: entry.technique,
              name: techniqueName(entry.technique) ?? entry.technique,
              count: entry.alerts,
            })}
            className="flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-accent/40 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none focus-visible:ring-inset"
          >
            <span className="flex items-baseline justify-between gap-3">
              <span className="flex min-w-0 items-baseline gap-2">
                <span className="font-mono text-xs text-brand">{entry.technique}</span>
                <span className="truncate text-xs text-muted-foreground">{techniqueName(entry.technique)}</span>
              </span>
              <span className="font-mono text-xs tabular-nums">{format.number(entry.alerts)}</span>
            </span>
            <span aria-hidden className="h-1.5 rounded-full bg-muted">
              <span
                className="block h-full rounded-full bg-brand"
                style={{ width: `${(entry.alerts / largest) * 100}%` }}
              />
            </span>
          </Link>
        </li>
      ))}
    </ol>
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
      <p className="rounded-md border px-4 py-4 text-muted-foreground">
        {t('orgOverview.noSources')}
      </p>
    )
  }

  const largest = Math.max(...sources.map((source) => source.failed_logins))
  return (
    <ol aria-label={t('orgOverview.sources')} className="flex flex-col rounded-md border">
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
