import { lazy } from 'react'

// Organization pages are only for operators, so they load as separate chunks
// and stay out of the bundle every user downloads.

export const OrgEventsPage = lazy(() =>
  import('./OrgEventsPage').then((module) => ({ default: module.OrgEventsPage })),
)

export const OrgAuditPage = lazy(() =>
  import('./OrgAuditPage').then((module) => ({ default: module.OrgAuditPage })),
)
