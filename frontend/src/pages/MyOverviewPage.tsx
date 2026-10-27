import type { ReactNode } from 'react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ActivityTable } from '@/features/account/ActivityTable'
import { ALERT_SEVERITIES } from '@/features/account/api'
import { useMyActivitySummary, useMySessions } from '@/features/account/hooks'
import { useCurrentUser } from '@/features/auth/hooks'
import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

const ALERT_WINDOW_DAYS = 30
const ALERT_PAGE_SIZE = 50
const RECENT_ALERTS = 5

export function MyOverviewPage() {
  const { t, i18n } = useTranslation()
  const { data: user } = useCurrentUser()

  if (user === undefined) {
    return null
  }

  const memberSince = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'long' }).format(
    new Date(user.created_at),
  )

  const rows: { label: string; value: string }[] = [
    { label: t('overview.username'), value: user.username },
    { label: t('overview.email'), value: user.email },
    { label: t('overview.role'), value: t(`roles.${user.role}`) },
    { label: t('overview.memberSince'), value: memberSince },
  ]

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t('nav.myProfile')} />

      <SecuritySummary />

      <section aria-labelledby="account-details" className="flex flex-col gap-3">
        <h2 id="account-details" className="text-base font-semibold">
          {t('overview.profile')}
        </h2>
        <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-[max-content_1fr]">
          {rows.map((row) => (
            <div key={row.label} className="contents">
              <dt className="text-muted-foreground">{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
          <dt className="text-muted-foreground">{t('overview.status')}</dt>
          <dd>
            <span className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium text-sev-ok bg-sev-ok-bg">
              <span aria-hidden className="size-1.5 rounded-full bg-sev-ok" />
              {t('overview.active')}
            </span>
          </dd>
        </dl>
      </section>
    </div>
  )
}

function SecuritySummary() {
  const { t } = useTranslation()
  const format = useFormatters()
  // Fixed for the life of the page, so the query key stays stable.
  const [since] = useState(() =>
    new Date(Date.now() - ALERT_WINDOW_DAYS * 24 * 60 * 60 * 1000).toISOString(),
  )

  const sessions = useMySessions()
  // The newest sign-in is this one; the one before it is worth checking.
  const logins = useMyActivitySummary({ eventType: ['login_success'], limit: 2 })
  const alerts = useMyActivitySummary({
    severity: ALERT_SEVERITIES,
    since,
    limit: ALERT_PAGE_SIZE,
  })

  const previousLogin = logins.data?.items[1]
  const alertItems = alerts.data?.items ?? []
  const alertCount = alerts.data
    ? `${alertItems.length}${alerts.data.next_cursor !== null ? '+' : ''}`
    : null

  return (
    <section aria-labelledby="security-summary" className="flex flex-col gap-4">
      <h2 id="security-summary" className="text-base font-semibold">
        {t('overview.security')}
      </h2>

      <dl className="grid gap-px border-y bg-border sm:grid-cols-3">
        <Stat label={t('overview.activeSessions')} query={sessions}>
          <span className="text-2xl font-semibold tabular-nums">{sessions.data?.length}</span>
          <Link to="/me/sessions" className="text-xs text-brand underline-offset-4 hover:underline">
            {t('overview.manageSessions')}
          </Link>
        </Stat>

        <Stat label={t('overview.previousLogin')} query={logins}>
          {previousLogin ? (
            <>
              <time
                dateTime={previousLogin.created_at}
                title={format.dateTime(previousLogin.created_at)}
                className="text-base font-medium"
              >
                {format.relative(previousLogin.created_at)}
              </time>
              <span className="font-mono text-xs text-muted-foreground">
                {previousLogin.ip_address ?? '—'}
              </span>
            </>
          ) : (
            <span className="text-muted-foreground">{t('overview.firstLogin')}</span>
          )}
        </Stat>

        <Stat label={t('overview.alerts')} query={alerts}>
          <span
            className={cn(
              'text-2xl font-semibold tabular-nums',
              alertItems.length > 0 ? 'text-sev-warn' : 'text-sev-ok',
            )}
          >
            {alertCount}
          </span>
        </Stat>
      </dl>

      {alerts.isSuccess && (
        <div className="flex flex-col gap-3">
          <h3 className="font-semibold">{t('overview.recentAlerts')}</h3>
          {alertItems.length === 0 ? (
            <p className="rounded-lg border bg-card px-4 py-4 text-muted-foreground">
              {t('overview.noAlerts')}
            </p>
          ) : (
            <div className="flex flex-col items-start gap-3">
              <ActivityTable events={alertItems.slice(0, RECENT_ALERTS)} />
              <Button asChild variant="outline" size="sm">
                <Link to="/me/activity?filter=alerts">{t('overview.viewAlerts')}</Link>
              </Button>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

interface StatProps {
  label: string
  query: { isPending: boolean; isError: boolean }
  children: ReactNode
}

function Stat({ label, query, children }: StatProps) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-0.5 bg-background px-4 py-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="flex flex-col items-start gap-1">
        {query.isPending ? (
          <Skeleton className="h-8 w-16" />
        ) : query.isError ? (
          <span className="text-muted-foreground">{t('overview.unavailable')}</span>
        ) : (
          children
        )}
      </dd>
    </div>
  )
}
