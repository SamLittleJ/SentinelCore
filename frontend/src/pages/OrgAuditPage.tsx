import { useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { PagedResults } from '@/components/PagedResults'
import { Button } from '@/components/ui/button'
import { AUDIT_EVENT_TYPES, type AuditEventType, type AuditLog } from '@/features/org/api'
import {
  hasNarrowingFilters,
  type LogFilters,
  readLogFilters,
  writeLogFilters,
} from '@/features/org/filters'
import { auditLogsKey, useAuditLogs } from '@/features/org/hooks'
import { LogDetails } from '@/features/org/LogDetails'
import { LogFilterBar } from '@/features/org/LogFilterBar'
import { LogTable } from '@/features/org/LogTable'
import { accountLabel, accountLinks, narrowingActions, recordFields } from '@/features/org/records'
import { ApiError } from '@/lib/api'

export function OrgAuditPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const filters = useMemo(() => readLogFilters(params, AUDIT_EVENT_TYPES), [params])
  const logs = useAuditLogs(filters)
  const [selected, setSelected] = useState<AuditLog | null>(null)

  const describe = (type: AuditEventType) => t(`audit.types.${type}`)
  const applyFilters = (next: LogFilters<AuditEventType>) => {
    setSelected(null)
    setParams(writeLogFilters(next))
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold">{t('nav.auditLog')}</h1>
          <p className="max-w-prose text-muted-foreground">
            {t('audit.subtitle')} {t('audit.viewingIsAudited')}
          </p>
        </div>
        <Button
          variant="outline"
          // Back to the first page, with the time window measured from now.
          onClick={() => void queryClient.resetQueries({ queryKey: auditLogsKey })}
        >
          <RefreshCw aria-hidden />
          {t('orgLog.refresh')}
        </Button>
      </header>

      <LogFilterBar
        filters={filters}
        onChange={applyFilters}
        types={AUDIT_EVENT_TYPES}
        typeLabel={describe}
      />

      <PagedResults
        query={logs}
        empty={hasNarrowingFilters(filters) ? t('orgLog.emptyFiltered') : t('orgLog.empty')}
        errorMessage={(error) =>
          error instanceof ApiError && error.status === 422 ? t('orgLog.invalidFilter') : undefined
        }
      >
        {(items) => (
          <LogTable
            label={t('audit.tableLabel')}
            items={items}
            describe={(log) => describe(log.event_type)}
            onSelect={setSelected}
            columns={[
              {
                header: t('orgLog.account'),
                cell: (log) => accountLabel(log, t),
                className: 'max-w-56 truncate font-mono text-xs',
              },
              {
                header: t('orgLog.ipAddress'),
                cell: (log) => log.ip_address ?? t('orgLog.none'),
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
        fields={
          selected
            ? [
                ...recordFields(selected, t),
                { label: t('orgLog.message'), value: selected.message ?? t('orgLog.none'), mono: true },
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
