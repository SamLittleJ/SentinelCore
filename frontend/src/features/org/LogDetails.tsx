import { ArrowRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

export interface DetailField {
  label: string
  value: ReactNode
  // Technical values (addresses, ids, messages) use the monospace font.
  mono?: boolean
}

// Narrows the current list, or opens another page.
export type DetailAction = NarrowingAction | DetailLink
type NarrowingAction = { label: string; onClick: () => void }
type DetailLink = { label: string; to: string }

interface LogDetailsProps {
  record: { id: number; created_at: string } | null
  title: string
  badge?: ReactNode
  fields: DetailField[]
  actions: DetailAction[]
  onClose: () => void
}

/** One record's full details in a side panel, with actions that narrow the
 * log to what the record names or open the accounts it names. */
export function LogDetails({ record, title, badge, fields, actions, onClose }: LogDetailsProps) {
  const { t } = useTranslation()
  const format = useFormatters()
  const narrowing = actions.filter((action) => 'onClick' in action)
  const links = actions.filter((action) => 'to' in action)

  return (
    <Sheet open={record !== null} onOpenChange={(open) => !open && onClose()}>
      {record && (
        <SheetContent closeLabel={t('orgLog.close')}>
          <SheetHeader>
            <SheetTitle>{title}</SheetTitle>
            <SheetDescription>{t('orgLog.detailsDescription', { id: record.id })}</SheetDescription>
          </SheetHeader>

          <div className="flex flex-wrap items-center gap-3">
            {badge}
            <time dateTime={record.created_at} className="font-mono text-xs text-muted-foreground">
              {format.dateTime(record.created_at)} · {format.relative(record.created_at)}
            </time>
          </div>

          <dl className="flex flex-col gap-3 border-t pt-4 text-sm">
            {fields.map((field) => (
              <div key={field.label} className="flex flex-col gap-0.5">
                <dt className="text-xs text-muted-foreground">{field.label}</dt>
                <dd className={cn('break-words', field.mono && 'font-mono text-xs')}>{field.value}</dd>
              </div>
            ))}
          </dl>

          {narrowing.length > 0 && (
            <div className="flex flex-wrap gap-2 border-t pt-4">
              {narrowing.map((action) => (
                <Button key={action.label} variant="outline" size="sm" onClick={action.onClick}>
                  {action.label}
                </Button>
              ))}
            </div>
          )}

          {links.length > 0 && (
            <div className="flex flex-wrap gap-2 border-t pt-4">
              {links.map((link) => (
                <Button key={link.label} asChild variant="secondary" size="sm">
                  <Link to={link.to}>
                    {link.label}
                    <ArrowRight aria-hidden />
                  </Link>
                </Button>
              ))}
            </div>
          )}
        </SheetContent>
      )}
    </Sheet>
  )
}
