import { lazy } from 'react'

// Organization pages are only for operators, so they load as separate chunks
// and stay out of the bundle every user downloads.

export const OrgOverviewPage = lazy(() =>
  import('./OrgOverviewPage').then((module) => ({ default: module.OrgOverviewPage })),
)

export const OrgEventsPage = lazy(() =>
  import('./OrgEventsPage').then((module) => ({ default: module.OrgEventsPage })),
)

export const OrgAuditPage = lazy(() =>
  import('./OrgAuditPage').then((module) => ({ default: module.OrgAuditPage })),
)

export const OrgUsersPage = lazy(() =>
  import('./OrgUsersPage').then((module) => ({ default: module.OrgUsersPage })),
)

export const OrgApiKeysPage = lazy(() =>
  import('./OrgApiKeysPage').then((module) => ({ default: module.OrgApiKeysPage })),
)

export const OrgUserPage = lazy(() =>
  import('./OrgUserPage').then((module) => ({ default: module.OrgUserPage })),
)
