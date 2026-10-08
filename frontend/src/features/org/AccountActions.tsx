import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { SegmentedControl } from '@/components/SegmentedControl'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { User } from '@/features/auth/api'
import { ApiError } from '@/lib/api'
import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

import {
  ASSIGNABLE_ROLES,
  type AssignableRole,
  changeUserRole,
  changeUserStatus,
  LOCK_DURATIONS,
  type LockDuration,
  lockUser,
  unlockUser,
} from './api'
import { useAccountChange, useRevokeUserSessions } from './hooks'
import { accountActions } from './permissions'

type ActionName = 'revokeSessions' | 'lock' | 'unlock' | 'deactivate' | 'activate' | 'changeRole'

type Notice = { tone: 'ok' | 'error'; text: string }

// The API's bounds for a containment reason, after trimming.
const REASON_MIN = 3
const REASON_MAX = 500

/**
 * The actions the signed-in operator may take on `account`. Each opens a
 * form in the page that names its effect and asks for confirmation; the
 * containment actions also ask for a reason.
 */
export function AccountActions({ actor, account }: { actor: User; account: User }) {
  const { t } = useTranslation()
  const format = useFormatters()
  const { actions, restriction } = accountActions(actor, account)
  const [open, setOpen] = useState<ActionName | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)

  const revoke = useRevokeUserSessions(account.id)
  const lock = useAccountChange(account.id, (input: { hours: LockDuration; reason: string }) =>
    lockUser(account.id, input.hours, input.reason),
  )
  const unlock = useAccountChange(account.id, () => unlockUser(account.id))
  const status = useAccountChange(account.id, (isActive: boolean) =>
    changeUserStatus(account.id, isActive),
  )
  const role = useAccountChange(account.id, (next: AssignableRole) =>
    changeUserRole(account.id, next),
  )
  const pending = [revoke, lock, unlock, status, role].some((mutation) => mutation.isPending)

  if (restriction) {
    return (
      <p className="rounded-lg border bg-card px-4 py-3 text-muted-foreground">
        {restriction === 'self' ? t('userDetail.selfNote') : t('userDetail.ownerNote')}
      </p>
    )
  }

  const available: { name: ActionName; label: string }[] = []
  if (actions.revokeSessions) available.push({ name: 'revokeSessions', label: t('userDetail.revokeSessions') })
  if (actions.lock) available.push({ name: 'lock', label: t('userDetail.lock') })
  if (actions.unlock) available.push({ name: 'unlock', label: t('userDetail.unlock') })
  if (actions.changeStatus) {
    available.push(
      account.is_active
        ? { name: 'deactivate', label: t('userDetail.deactivate') }
        : { name: 'activate', label: t('userDetail.activate') },
    )
  }
  if (actions.changeRole) available.push({ name: 'changeRole', label: t('userDetail.changeRole') })

  const settle = (text: string) => {
    setOpen(null)
    setNotice({ tone: 'ok', text })
  }
  const fail = (error: Error) =>
    setNotice({
      tone: 'error',
      text:
        error instanceof ApiError && error.status === 403
          ? t('userDetail.actionForbidden')
          : t('userDetail.actionFailed'),
    })
  const start = (name: ActionName) => {
    setNotice(null)
    setOpen(name)
  }
  const cancel = () => setOpen(null)

  const forms: Record<ActionName, () => ReactNode> = {
    revokeSessions: () => (
      <ReasonForm
        title={t('userDetail.revokeSessions')}
        help={t('userDetail.revokeSessionsHelp')}
        pending={pending}
        onCancel={cancel}
        onConfirm={({ reason }) =>
          revoke.mutate(reason, {
            onSuccess: ({ revoked_sessions }) =>
              settle(t('userDetail.sessionsRevoked', { count: revoked_sessions })),
            onError: fail,
          })
        }
      />
    ),
    lock: () => (
      <ReasonForm
        title={t('userDetail.lock')}
        help={t('userDetail.lockHelp')}
        withDuration
        pending={pending}
        onCancel={cancel}
        onConfirm={({ reason, hours }) =>
          lock.mutate(
            { hours, reason },
            {
              onSuccess: (user) =>
                settle(
                  t('userDetail.lockedDone', {
                    time: user.locked_until ? format.dateTime(user.locked_until) : '',
                  }),
                ),
              onError: fail,
            },
          )
        }
      />
    ),
    unlock: () => (
      <ConfirmForm
        title={t('userDetail.unlock')}
        help={t('userDetail.unlockHelp')}
        pending={pending}
        onCancel={cancel}
        onConfirm={() =>
          unlock.mutate(undefined, {
            onSuccess: () => settle(t('userDetail.unlockedDone')),
            onError: fail,
          })
        }
      />
    ),
    deactivate: () => (
      <ConfirmForm
        title={t('userDetail.deactivate')}
        help={t('userDetail.deactivateHelp')}
        destructive
        pending={pending}
        onCancel={cancel}
        onConfirm={() =>
          status.mutate(false, {
            onSuccess: () => settle(t('userDetail.deactivatedDone')),
            onError: fail,
          })
        }
      />
    ),
    activate: () => (
      <ConfirmForm
        title={t('userDetail.activate')}
        help={t('userDetail.activateHelp')}
        pending={pending}
        onCancel={cancel}
        onConfirm={() =>
          status.mutate(true, {
            onSuccess: () => settle(t('userDetail.activatedDone')),
            onError: fail,
          })
        }
      />
    ),
    changeRole: () => (
      <RoleForm
        current={account.role}
        pending={pending}
        onCancel={cancel}
        onConfirm={(next) =>
          role.mutate(next, {
            onSuccess: (user) =>
              settle(t('userDetail.roleChangedDone', { role: t(`roles.${user.role}`) })),
            onError: fail,
          })
        }
      />
    ),
  }

  return (
    <div className="flex flex-col gap-3">
      {open === null ? (
        <div className="flex flex-wrap gap-2">
          {available.map((action) => (
            <Button key={action.name} variant="outline" onClick={() => start(action.name)}>
              {action.label}
            </Button>
          ))}
        </div>
      ) : (
        forms[open]()
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
    </div>
  )
}

interface FormFrameProps {
  title: string
  help: string
  children?: ReactNode
  confirmDisabled?: boolean
  destructive?: boolean
  pending: boolean
  onCancel: () => void
  onSubmit: () => void
}

/** A confirmation step in the page, not a dialog, like the other actions
 * that end sessions. */
function FormFrame({
  title,
  help,
  children,
  confirmDisabled = false,
  destructive = false,
  pending,
  onCancel,
  onSubmit,
}: FormFrameProps) {
  const { t } = useTranslation()
  const titleId = useId()
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmit()
  }

  return (
    <form
      aria-labelledby={titleId}
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-lg border border-sev-warn/40 bg-sev-warn-bg/40 px-4 py-4"
    >
      <div className="flex flex-col gap-1">
        <h3 id={titleId} className="font-medium">
          {title}
        </h3>
        <p className="text-sm text-muted-foreground">{help}</p>
      </div>
      {children}
      <div className="flex gap-2">
        <Button
          type="submit"
          variant={destructive ? 'destructive' : 'default'}
          disabled={confirmDisabled || pending}
          // A form without fields starts on its confirmation.
          autoFocus={children === undefined}
        >
          {t('userDetail.confirm')}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t('userDetail.cancel')}
        </Button>
      </div>
    </form>
  )
}

function ConfirmForm(props: Omit<FormFrameProps, 'onSubmit' | 'children'> & { onConfirm: () => void }) {
  const { onConfirm, ...frame } = props
  return <FormFrame {...frame} onSubmit={onConfirm} />
}

interface ReasonFormProps {
  title: string
  help: string
  withDuration?: boolean
  pending: boolean
  onCancel: () => void
  onConfirm: (input: { reason: string; hours: LockDuration }) => void
}

function ReasonForm({ title, help, withDuration = false, pending, onCancel, onConfirm }: ReasonFormProps) {
  const { t } = useTranslation()
  const reasonId = useId()
  const helpId = useId()
  const [reason, setReason] = useState('')
  const [hours, setHours] = useState<LockDuration>(24)
  const trimmed = reason.trim()
  const valid = trimmed.length >= REASON_MIN && trimmed.length <= REASON_MAX

  const durationOptions = LOCK_DURATIONS.map((value) => ({
    value: String(value) as `${LockDuration}`,
    label: t(`userDetail.durations.${value}`),
  }))

  return (
    <FormFrame
      title={title}
      help={help}
      destructive
      confirmDisabled={!valid}
      pending={pending}
      onCancel={onCancel}
      onSubmit={() => onConfirm({ reason: trimmed, hours })}
    >
      {withDuration && (
        <SegmentedControl
          label={t('userDetail.duration')}
          options={durationOptions}
          value={String(hours) as `${LockDuration}`}
          onChange={(value) => setHours(Number(value) as LockDuration)}
        />
      )}
      <div className="flex flex-col gap-1.5">
        <label htmlFor={reasonId} className="text-sm font-medium">
          {t('userDetail.reason')}
        </label>
        <Textarea
          id={reasonId}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={REASON_MAX}
          aria-describedby={helpId}
          autoFocus
          className="max-w-xl bg-background"
        />
        <p id={helpId} className="text-xs text-muted-foreground">
          {t('userDetail.reasonHelp')}
        </p>
      </div>
    </FormFrame>
  )
}

function RoleForm({
  current,
  pending,
  onCancel,
  onConfirm,
}: {
  current: string
  pending: boolean
  onCancel: () => void
  onConfirm: (role: AssignableRole) => void
}) {
  const { t } = useTranslation()
  const [role, setRole] = useState<AssignableRole>(
    ASSIGNABLE_ROLES.find((option) => option === current) ?? 'user',
  )

  return (
    <FormFrame
      title={t('userDetail.changeRole')}
      help={t('userDetail.changeRoleHelp')}
      confirmDisabled={role === current}
      pending={pending}
      onCancel={onCancel}
      onSubmit={() => onConfirm(role)}
    >
      <SegmentedControl
        label={t('userDetail.newRole')}
        options={ASSIGNABLE_ROLES.map((option) => ({ value: option, label: t(`roles.${option}`) }))}
        value={role}
        onChange={setRole}
      />
    </FormFrame>
  )
}
