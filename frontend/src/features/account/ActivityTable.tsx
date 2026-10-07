import { useTranslation } from 'react-i18next'

import { SeverityBadge } from '@/components/SeverityBadge'
import { useFormatters } from '@/lib/format'

import { type ActivityEvent, isAccountAction } from './api'

export function ActivityTable({ events }: { events: ActivityEvent[] }) {
  const { t } = useTranslation()
  const format = useFormatters()

  // Account actions read differently for the operator and for the account.
  const describe = (event: ActivityEvent) =>
    event.as_target && isAccountAction(event.event_type)
      ? t(`eventsAsTarget.${event.event_type}`)
      : t(`events.${event.event_type}`)

  return (
    <div className="w-full overflow-x-auto rounded-lg border bg-card">
      <table aria-label={t('activity.tableLabel')} className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('activity.event')}
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('activity.severity')}
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('activity.ipAddress')}
            </th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">
              {t('activity.time')}
            </th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id} className="border-b last:border-b-0">
              <td className="min-w-56 px-4 py-2.5">{describe(event)}</td>
              <td className="px-4 py-2.5">
                <SeverityBadge severity={event.severity} />
              </td>
              <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                {event.ip_address ?? '—'}
              </td>
              <td className="px-4 py-2.5 text-right whitespace-nowrap text-muted-foreground">
                <time dateTime={event.created_at} title={format.relative(event.created_at)}>
                  {format.dateTime(event.created_at)}
                </time>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
