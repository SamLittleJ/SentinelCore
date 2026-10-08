import { useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { PagedResults } from '@/components/PagedResults'
import { SeverityBadge } from '@/components/SeverityBadge'
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
import { accountLabel, accountLinks, narrowingActions, recordFields } from '@/features/org/records'
import { ApiError } from '@/lib/api'

export function OrgEventsPage() {
  const { t } = useTranslation()
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
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold">{t('nav.securityEvents')}</h1>
          <p className="max-w-prose text-muted-foreground">{t('orgEvents.subtitle')}</p>
        </div>
        <Button
          variant="outline"
          // Back to the first page, with the time window measured from now.
          onClick={() => void queryClient.resetQueries({ queryKey: securityEventsKey })}
        >
          <RefreshCw aria-hidden />
          {t('orgLog.refresh')}
        </Button>
      </header>

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
        fields={
          selected
            ? [
                ...recordFields(selected, t),
                { label: t('orgLog.source'), value: selected.source, mono: true },
                { label: t('orgLog.message'), value: selected.message, mono: true },
              ]
            : []
        }
        actions={
          selected
            ? [...narrowingActions(selected, filters, applyFilters, t), ...accountLinks(selected, t)]
            : []
        }
      />
    </div>
  )
}
