import type { TFunction } from 'i18next'

import type { DetailAction, DetailField } from './LogDetails'
import type { LogFilters } from './filters'

/** The fields both logs share. */
export interface LogRecord {
  user_id: number | null
  target_user_id: number | null
  email: string | null
  ip_address: string | null
}

/** The account a record names: its email, else its user id. */
export function accountLabel(record: LogRecord, t: TFunction): string {
  if (record.email) return record.email
  return record.user_id === null ? t('orgLog.none') : t('orgLog.userRef', { id: record.user_id })
}

export function recordFields(record: LogRecord, t: TFunction): DetailField[] {
  const account =
    record.email && record.user_id !== null
      ? `${record.email} (${t('orgLog.userRef', { id: record.user_id })})`
      : accountLabel(record, t)
  return [
    { label: t('orgLog.account'), value: account, mono: true },
    {
      label: t('orgLog.target'),
      value:
        record.target_user_id === null
          ? t('orgLog.none')
          : t('orgLog.userRef', { id: record.target_user_id }),
      mono: true,
    },
    { label: t('orgLog.ipAddress'), value: record.ip_address ?? t('orgLog.none'), mono: true },
  ]
}

/** Actions that narrow the log to what `record` names. Each keeps the other
 * filters and replaces the one it sets. */
export function narrowingActions<Type extends string>(
  record: LogRecord,
  filters: LogFilters<Type>,
  apply: (filters: LogFilters<Type>) => void,
  t: TFunction,
): DetailAction[] {
  const actions: DetailAction[] = []
  if (record.user_id !== null) {
    actions.push({
      label: t('orgLog.filterAccount'),
      onClick: () => apply({ ...filters, userId: record.user_id ?? undefined }),
    })
  } else if (record.email) {
    // A failed sign-in names an email but no account.
    actions.push({
      label: t('orgLog.filterAccount'),
      onClick: () => apply({ ...filters, search: record.email ?? '' }),
    })
  }
  if (record.target_user_id !== null) {
    actions.push({
      label: t('orgLog.filterTarget'),
      onClick: () => apply({ ...filters, targetUserId: record.target_user_id ?? undefined }),
    })
  }
  if (record.ip_address) {
    actions.push({
      label: t('orgLog.filterIp'),
      onClick: () => apply({ ...filters, search: record.ip_address ?? '' }),
    })
  }
  return actions
}
