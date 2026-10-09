import { CircleHelp, Monitor, Smartphone, type LucideIcon } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { Session } from '@/features/account/api'
import { useMySessions, useRevokeOtherSessions, useRevokeSession } from '@/features/account/hooks'
import { type DeviceKind, describeUserAgent } from '@/features/account/user-agent'
import { useLogOut } from '@/features/auth/hooks'
import { ApiError } from '@/lib/api'
import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

const DEVICE_ICONS: Record<DeviceKind, LucideIcon> = {
  desktop: Monitor,
  mobile: Smartphone,
  unknown: CircleHelp,
}

type Notice = { tone: 'ok' | 'error'; text: string }

export function MySessionsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const sessions = useMySessions()
  const revokeSession = useRevokeSession()
  const revokeOthers = useRevokeOtherSessions()
  const logOut = useLogOut()
  // The session id awaiting confirmation, or 'others' for the bulk action.
  const [confirming, setConfirming] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)

  // This browser first, then the rest newest first (the API's order).
  const list = [...(sessions.data ?? [])].sort((a, b) => Number(b.current) - Number(a.current))
  const otherCount = list.filter((session) => !session.current).length

  function handleRevoke(sessionId: string) {
    setNotice(null)
    revokeSession.mutate(sessionId, {
      onSuccess: () => setNotice({ tone: 'ok', text: t('sessions.revoked') }),
      onError: (error) =>
        setNotice(
          error instanceof ApiError && error.status === 404
            ? { tone: 'ok', text: t('sessions.alreadyGone') }
            : { tone: 'error', text: t('sessions.actionFailed') },
        ),
      onSettled: () => setConfirming(null),
    })
  }

  function handleRevokeOthers() {
    setNotice(null)
    revokeOthers.mutate(undefined, {
      onSuccess: ({ revoked_sessions }) =>
        setNotice({ tone: 'ok', text: t('sessions.othersRevoked', { count: revoked_sessions }) }),
      onError: () => setNotice({ tone: 'error', text: t('sessions.actionFailed') }),
      onSettled: () => setConfirming(null),
    })
  }

  function handleLogOut() {
    logOut.mutate(undefined, {
      onSettled: () => void navigate('/login', { replace: true }),
    })
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t('nav.mySessions')}
        description={t('sessions.subtitle')}
        actions={
          <>
            {confirming !== 'others' && (
              <Button
                variant="outline"
                disabled={otherCount === 0 || revokeOthers.isPending}
                onClick={() => {
                  setNotice(null)
                  setConfirming('others')
                }}
              >
                {t('sessions.revokeOthers')}
              </Button>
            )}
          </>
        }
      />

      {confirming === 'others' && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-sev-warn/40 bg-sev-warn-bg px-4 py-3">
          <p>{t('sessions.revokeOthersQuestion')}</p>
          <div className="flex gap-2">
            <Button
              variant="destructive"
              size="sm"
              autoFocus
              disabled={revokeOthers.isPending}
              onClick={handleRevokeOthers}
            >
              {t('sessions.revokeOthersConfirm')}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
              {t('sessions.cancel')}
            </Button>
          </div>
        </div>
      )}

      {notice && (
        <p
          role={notice.tone === 'error' ? 'alert' : 'status'}
          className={cn(
            'rounded-lg px-4 py-3',
            notice.tone === 'error'
              ? 'bg-sev-incident-bg text-sev-incident'
              : 'bg-sev-ok-bg text-sev-ok',
          )}
        >
          {notice.text}
        </p>
      )}

      {sessions.isPending ? (
        <div className="flex flex-col gap-2" role="status" aria-label={t('app.loading')}>
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : sessions.isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border px-4 py-4">
          <p className="text-muted-foreground">{t('errors.loadFailedBody')}</p>
          <Button variant="outline" size="sm" onClick={() => void sessions.refetch()}>
            {t('errors.retry')}
          </Button>
        </div>
      ) : (
        <ul aria-label={t('sessions.listLabel')} className="flex flex-col divide-y rounded-lg border bg-card">
          {list.map((session) => (
            <SessionRow
              key={session.id}
              session={session}
              confirming={confirming === session.id}
              pending={revokeSession.isPending && revokeSession.variables === session.id}
              onAskRevoke={() => {
                setNotice(null)
                setConfirming(session.id)
              }}
              onCancel={() => setConfirming(null)}
              onRevoke={() => handleRevoke(session.id)}
              onLogOut={handleLogOut}
              loggingOut={logOut.isPending}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

interface SessionRowProps {
  session: Session
  confirming: boolean
  pending: boolean
  loggingOut: boolean
  onAskRevoke: () => void
  onCancel: () => void
  onRevoke: () => void
  onLogOut: () => void
}

function SessionRow({
  session,
  confirming,
  pending,
  loggingOut,
  onAskRevoke,
  onCancel,
  onRevoke,
  onLogOut,
}: SessionRowProps) {
  const { t } = useTranslation()
  const format = useFormatters()
  const device = describeUserAgent(session.user_agent)
  const Icon = DEVICE_ICONS[device.kind]
  // Buttons repeat on every row, so each one names the session it acts on.
  const nameId = useId()

  const name =
    device.browser && device.os
      ? t('sessions.device', { browser: device.browser, os: device.os })
      : (device.browser ?? device.os ?? t('sessions.unknownDevice'))

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4">
      <Icon aria-hidden className="size-5 shrink-0 text-muted-foreground" />

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span id={nameId} className="font-medium" title={session.user_agent ?? undefined}>
            {name}
          </span>
          {session.current && (
            <span className="rounded bg-brand-tint px-2 py-0.5 text-xs font-medium text-brand">
              {t('sessions.current')}
            </span>
          )}
        </div>
        <dl className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
          <div className="flex gap-1.5">
            <dt>{t('sessions.ipAddress')}</dt>
            <dd className="font-mono text-foreground">
              {session.ip_address ?? t('sessions.unknownIp')}
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt>{t('sessions.started')}</dt>
            <dd className="text-foreground">
              <time dateTime={session.created_at} title={format.dateTime(session.created_at)}>
                {format.relative(session.created_at)}
              </time>
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt>{t('sessions.expires')}</dt>
            <dd className="text-foreground">
              <time dateTime={session.expires_at} title={format.dateTime(session.expires_at)}>
                {format.relative(session.expires_at)}
              </time>
            </dd>
          </div>
        </dl>
      </div>

      <div className="flex gap-2">
        {session.current ? (
          <Button variant="outline" size="sm" disabled={loggingOut} onClick={onLogOut}>
            {t('sessions.logOutHere')}
          </Button>
        ) : confirming ? (
          <>
            <Button
              variant="destructive"
              size="sm"
              autoFocus
              aria-describedby={nameId}
              disabled={pending}
              onClick={onRevoke}
            >
              {t('sessions.revokeConfirm')}
            </Button>
            <Button variant="ghost" size="sm" onClick={onCancel}>
              {t('sessions.cancel')}
            </Button>
          </>
        ) : (
          <Button variant="outline" size="sm" aria-describedby={nameId} onClick={onAskRevoke}>
            {t('sessions.revoke')}
          </Button>
        )}
      </div>
    </li>
  )
}
