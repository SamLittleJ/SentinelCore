import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useParams } from 'react-router'

import { PagedResults } from '@/components/PagedResults'
import { SeverityBadge } from '@/components/SeverityBadge'
import { StatusPage } from '@/components/StatusPage'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { User } from '@/features/auth/api'
import { useCurrentUser } from '@/features/auth/hooks'
import { AccountActions } from '@/features/org/AccountActions'
import { AccountState } from '@/features/org/AccountState'
import type { SecurityEvent } from '@/features/org/api'
import { useUser, useUserActivity } from '@/features/org/hooks'
import { LogDetails } from '@/features/org/LogDetails'
import { LogTable } from '@/features/org/LogTable'
import { accountLabel, accountLinks, recordFields } from '@/features/org/records'
import type { UserPageState } from '@/features/org/user-filters'
import { ApiError } from '@/lib/api'
import { useFormatters } from '@/lib/format'

function parseUserId(value: string | undefined): number | null {
  return value !== undefined && /^[1-9]\d*$/.test(value) ? Number(value) : null
}

export function OrgUserPage() {
  const { userId } = useParams()
  const id = parseUserId(userId)
  return id === null ? <AccountNotFound /> : <AccountPage key={id} userId={id} />
}

function BackLink() {
  const { t } = useTranslation()
  const location = useLocation()
  // Back to the list as it was filtered, when the account was opened from it.
  const from = (location.state as UserPageState | null)?.from ?? '/org/users'
  return (
    <Link
      to={from}
      className="inline-flex w-fit items-center gap-1.5 rounded-sm text-sm text-muted-foreground hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <ArrowLeft aria-hidden className="size-4" />
      {t('userDetail.back')}
    </Link>
  )
}

function AccountNotFound() {
  const { t } = useTranslation()
  return (
    <StatusPage
      title={t('userDetail.notFoundTitle')}
      body={t('userDetail.notFoundBody')}
      action={
        <Button asChild variant="outline">
          <Link to="/org/users">{t('userDetail.back')}</Link>
        </Button>
      }
    />
  )
}

function AccountPage({ userId }: { userId: number }) {
  const { t } = useTranslation()
  const { data: actor } = useCurrentUser()
  const account = useUser(userId)

  if (account.isError && account.error instanceof ApiError && account.error.status === 404) {
    return <AccountNotFound />
  }

  return (
    <div className="flex flex-col gap-6">
      <BackLink />

      {account.isPending ? (
        <div role="status" aria-label={t('app.loading')} className="flex flex-col gap-3">
          <Skeleton className="h-7 w-56" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : account.isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border px-4 py-4">
          <p className="text-muted-foreground">{t('errors.loadFailedBody')}</p>
          <Button variant="outline" size="sm" onClick={() => void account.refetch()}>
            {t('errors.retry')}
          </Button>
        </div>
      ) : (
        <>
          <AccountHeader account={account.data} />
          {actor && (
            <section aria-labelledby="account-actions" className="flex flex-col gap-3">
              <h2 id="account-actions" className="font-semibold">
                {t('userDetail.actions')}
              </h2>
              <AccountActions actor={actor} account={account.data} />
            </section>
          )}
        </>
      )}

      <AccountHistory userId={userId} />
    </div>
  )
}

function AccountHeader({ account }: { account: User }) {
  const { t } = useTranslation()
  const format = useFormatters()

  const fields = [
    { label: t('userDetail.id'), value: account.id, mono: true },
    { label: t('userDetail.role'), value: t(`roles.${account.role}`) },
    { label: t('userDetail.memberSince'), value: format.date(account.created_at) },
    { label: t('userDetail.updated'), value: format.dateTime(account.updated_at) },
  ]

  return (
    <header className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-xl font-semibold">{account.username}</h1>
        <p className="font-mono text-sm text-muted-foreground">{account.email}</p>
        <AccountState user={account} detailed />
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-lg border bg-card px-4 py-4 text-sm sm:grid-cols-4">
        {fields.map((field) => (
          <div key={field.label} className="flex flex-col gap-0.5">
            <dt className="text-xs text-muted-foreground">{field.label}</dt>
            <dd className={field.mono ? 'font-mono text-xs' : undefined}>{field.value}</dd>
          </div>
        ))}
      </dl>
    </header>
  )
}

function AccountHistory({ userId }: { userId: number }) {
  const { t } = useTranslation()
  const activity = useUserActivity(userId)
  const [selected, setSelected] = useState<SecurityEvent | null>(null)
  const describe = (event: SecurityEvent) => t(`orgEvents.types.${event.event_type}`)

  return (
    <section aria-labelledby="account-history" className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 id="account-history" className="font-semibold">
          {t('userDetail.activity')}
        </h2>
        <p className="max-w-prose text-sm text-muted-foreground">{t('userDetail.activityHelp')}</p>
      </div>

      <PagedResults query={activity} empty={t('userDetail.activityEmpty')}>
        {(items) => (
          <LogTable
            label={t('userDetail.activity')}
            items={items}
            describe={describe}
            onSelect={setSelected}
            columns={[
              {
                header: t('orgLog.severity'),
                cell: (event) => <SeverityBadge severity={event.severity} />,
              },
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
      </PagedResults>

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
        actions={selected ? accountLinks(selected, t, userId) : []}
      />
    </section>
  )
}
