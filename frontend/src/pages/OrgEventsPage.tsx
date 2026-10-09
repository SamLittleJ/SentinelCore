import { useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { PagedResults } from '@/components/PagedResults'
import { SeverityBadge } from '@/components/SeverityBadge'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { SECURITY_EVENT_TYPES, type SecurityEventType } from '@/features/account/api'
import type { SecurityEvent } from '@/features/org/api'
import {
  hasNarrowingFilters,
  type LogFilters,
  readLogFilters,
  writeLogFilters,
} from '@/features/org/filters'
import { securityEventsKey, useSecurityEvents } from '@/features/org/hooks'
import { LogDetails } from '@/features/org/LogDetails'
import { LogFilterBar } from '@/features/org/LogFilterBar'
import { LogTable } from '@/features/org/LogTable'
import { accountLabel, accountLinks, narrowingActions } from '@/features/org/records'
import { securityEventFields, techniqueBadge } from '@/features/org/security-event-fields'
import { ApiError } from '@/lib/api'
import { useFormatters } from '@/lib/format'

export function OrgEventsPage() {
  const { t } = useTranslation()
  const format = useFormatters()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const filters = useMemo(() => readLogFilters(params, SECURITY_EVENT_TYPES), [params])
  const events = useSecurityEvents(filters)
  const [selected, setSelected] = useState<SecurityEvent | null>(null)

  const describe = (type: SecurityEventType) => t(`orgEvents.types.${type}`)
  const applyFilters = (next: LogFilters<SecurityEventType>) => {
    setSelected(null)
    setParams(writeLogFilters(next))
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t('nav.securityEvents')}
        description={t('orgEvents.subtitle')}
        actions={
          <Button
            variant="outline"
            // Back to the first page, with the time window measured from now.
            onClick={() => void queryClient.resetQueries({ queryKey: securityEventsKey })}
          >
            <RefreshCw aria-hidden />
            {t('orgLog.refresh')}
          </Button>
        }
      />

      <LogFilterBar
        filters={filters}
        onChange={applyFilters}
        types={SECURITY_EVENT_TYPES}
        typeLabel={describe}
        withSeverity
      />

      <PagedResults
        query={events}
        empty={hasNarrowingFilters(filters) ? t('orgLog.emptyFiltered') : t('orgLog.empty')}
        errorMessage={(error) =>
          error instanceof ApiError && error.status === 422 ? t('orgLog.invalidFilter') : undefined
        }
      >
        {(items) => (
          <LogTable
            label={t('orgEvents.tableLabel')}
            items={items}
            describe={(event) => describe(event.event_type)}
            annotate={techniqueBadge}
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
        title={selected ? describe(selected.event_type) : ''}
        badge={selected && <SeverityBadge severity={selected.severity} />}
        fields={selected ? securityEventFields(selected, t, format) : []}
        actions={
          selected
            ? [...narrowingActions(selected, filters, applyFilters, t), ...accountLinks(selected, t)]
            : []
        }
      />
    </div>
  )
}
