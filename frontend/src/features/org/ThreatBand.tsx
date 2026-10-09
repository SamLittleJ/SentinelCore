import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { Severity } from '@/features/account/api'
import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

import type { SeverityBucket, SeverityCounts, ThreatLevel } from './api'
import { writeLogFilters } from './filters'
import { useSecuritySummary } from './hooks'

const LEVEL_STYLES: Record<ThreatLevel, { edge: string; dot: string; text: string }> = {
  calm: { edge: 'border-t-sev-ok', dot: 'bg-sev-ok', text: 'text-sev-ok' },
  warn: { edge: 'border-t-sev-warn', dot: 'bg-sev-warn', text: 'text-sev-warn' },
  incident: { edge: 'border-t-sev-incident', dot: 'bg-sev-incident', text: 'text-sev-incident' },
}

const CELL_STYLES: Record<Severity | 'none', string> = {
  none: 'bg-border',
  info: 'bg-sev-info/45',
  warn: 'bg-sev-warn/75',
  incident: 'bg-sev-incident',
}

/** The most severe kind of event in `counts`, or none. */
function topSeverity(counts: SeverityCounts): Severity | 'none' {
  if (counts.incident > 0) return 'incident'
  if (counts.warn > 0) return 'warn'
  if (counts.info > 0) return 'info'
  return 'none'
}

/** The organization's state at a glance, above every organization page:
 * the level, the last 24 hours hour by hour, and the latest detection.
 * Counts only, from the summary, which is not audited; the link opens the
 * event log, which is. */
export function ThreatBand() {
  const { t } = useTranslation()
  const format = useFormatters()
  const summary = useSecuritySummary()

  // The overview shows the loading state and the retry; the band waits.
  if (!summary.data) return null
  const data = summary.data
  const level = data.threat_level
  const styles = LEVEL_STYLES[level]
  const latest = data.latest_detection
  const latestTypes =
    latest && data.techniques_7d.find((entry) => entry.technique === latest.technique)?.event_types

  const cellLabel = (bucket: SeverityBucket) =>
    t('band.hour', {
      time: format.time(bucket.start),
      incident: bucket.counts.incident,
      warn: bucket.counts.warn,
      info: bucket.counts.info,
    })

  return (
    <section
      aria-label={t('band.label')}
      className={cn(
        'flex flex-wrap items-center gap-x-8 gap-y-3 border-t-[3px] border-b bg-sidebar/60 px-4 py-3 md:px-8',
        styles.edge,
      )}
    >
      <p className="flex min-w-44 items-center gap-2.5">
        <span aria-hidden className={cn('size-2.5 rounded-full ring-4 ring-current/20', styles.dot, styles.text)} />
        <span className={cn('label-mono', styles.text)}>{t(`band.levels.${level}`)}</span>
        <span className="sr-only">
          {t('band.totals', {
            incident: data.last_24h.incident,
            warn: data.last_24h.warn,
            info: data.last_24h.info,
          })}
        </span>
      </p>

      <div aria-hidden className="flex min-w-0 flex-[1_1_18rem] flex-col gap-1">
        <div className="grid h-4 grid-cols-24 gap-[3px]">
          {data.hourly.map((bucket) => (
            <span
              key={bucket.start}
              title={cellLabel(bucket)}
              className={cn('rounded-[2px]', CELL_STYLES[topSeverity(bucket.counts)])}
            />
          ))}
        </div>
        <div className="flex justify-between font-mono text-[10px] text-muted-foreground">
          <span>{t('band.dayAgo')}</span>
          <span>{t('band.now')}</span>
        </div>
      </div>

      <p className="label-mono tracking-normal text-muted-foreground normal-case">
        {latest ? (
          <>
            {t('band.latest')}{' '}
            <Link
              to={`/org/events?${writeLogFilters({
                range: '24h',
                types: latestTypes ?? [],
                severities: [],
                search: '',
              }).toString()}`}
              className="text-foreground underline-offset-4 hover:underline"
            >
              {latest.technique} · <time dateTime={latest.created_at}>{format.time(latest.created_at)}</time>
            </Link>
          </>
        ) : (
          t('band.noDetection')
        )}
      </p>
    </section>
  )
}
