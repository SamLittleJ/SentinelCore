import { Info, ShieldAlert, TriangleAlert, type LucideIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { Severity } from '@/features/account/api'
import { cn } from '@/lib/utils'

const STYLES: Record<Severity, { icon: LucideIcon; className: string }> = {
  info: { icon: Info, className: 'bg-sev-info-bg text-sev-info' },
  warn: { icon: TriangleAlert, className: 'bg-sev-warn-bg text-sev-warn' },
  incident: { icon: ShieldAlert, className: 'bg-sev-incident-bg text-sev-incident' },
}

/** Severity is always shown as icon + word, never by color alone. */
export function SeverityBadge({ severity }: { severity: Severity }) {
  const { t } = useTranslation()
  const { icon: Icon, className } = STYLES[severity]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        className,
      )}
    >
      <Icon aria-hidden className="size-3.5" />
      {t(`severity.${severity}`)}
    </span>
  )
}
