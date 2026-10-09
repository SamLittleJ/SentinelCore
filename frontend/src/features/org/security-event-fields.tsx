import type { TFunction } from 'i18next'

import type { useFormatters } from '@/lib/format'

import type { SecurityEvent } from './api'
import type { DetailField } from './LogDetails'
import { MitreBadge, TechniqueDetail } from './MitreBadge'
import { recordFields } from './records'

/** The badge beside a detection in a log: its MITRE ATT&CK technique. */
export function techniqueBadge(event: SecurityEvent) {
  return event.mitre_technique ? <MitreBadge technique={event.mitre_technique} /> : null
}

/** What a security event's details show, on every page that lists them. */
export function securityEventFields(
  event: SecurityEvent,
  t: TFunction,
  format: ReturnType<typeof useFormatters>,
): DetailField[] {
  const fields = recordFields(event, t)
  // An alert about an event reported late was raised after it happened.
  if (event.occurred_at && Date.parse(event.occurred_at) !== Date.parse(event.created_at)) {
    fields.push({
      label: t('orgLog.occurredAt'),
      value: `${format.dateTime(event.occurred_at)} · ${format.relative(event.occurred_at)}`,
      mono: true,
    })
  }
  if (event.mitre_technique) {
    fields.push({
      label: t('mitre.label'),
      value: <TechniqueDetail technique={event.mitre_technique} />,
    })
  }
  fields.push(
    { label: t('orgLog.source'), value: event.source, mono: true },
    { label: t('orgLog.message'), value: event.message, mono: true },
  )
  return fields
}
