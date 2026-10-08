import { useTranslation } from 'react-i18next'

import type { User } from '@/features/auth/api'
import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

import { isLockedNow } from './permissions'

const BADGE = 'inline-flex items-center rounded px-2 py-0.5 text-xs font-medium whitespace-nowrap'

/** Whether the account can sign in: active, deactivated, locked, or both of
 * the last two. Always a word, never color alone. */
export function AccountState({ user, detailed = false }: { user: User; detailed?: boolean }) {
  const { t } = useTranslation()
  const format = useFormatters()
  const locked = isLockedNow(user) ? user.locked_until : null

  return (
    <span className="inline-flex flex-wrap gap-1.5">
      {user.is_active ? (
        !locked && <span className={cn(BADGE, 'bg-sev-ok-bg text-sev-ok')}>{t('users.active')}</span>
      ) : (
        <span className={cn(BADGE, 'bg-muted text-muted-foreground')}>{t('users.inactive')}</span>
      )}
      {locked && (
        <span
          className={cn(BADGE, 'bg-sev-incident-bg text-sev-incident')}
          title={detailed ? undefined : format.dateTime(locked)}
        >
          {detailed
            ? t('users.lockedUntil', { time: format.dateTime(locked) })
            : t('users.locked')}
        </span>
      )}
    </span>
  )
}
