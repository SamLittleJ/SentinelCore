import { Navigate, type RouteObject } from 'react-router'

import { AppShell } from '@/components/layout/AppShell'
import { RequireAuth, RequireOrganizationAccess } from '@/features/auth/guards'
import { LoginPage } from '@/pages/LoginPage'
import { MyActivityPage } from '@/pages/MyActivityPage'
import { MyOverviewPage } from '@/pages/MyOverviewPage'
import { MySessionsPage } from '@/pages/MySessionsPage'
import { NotFoundPage, OrganizationOverviewPage } from '@/pages/SimplePages'
import { OrgAuditPage, OrgEventsPage, OrgUserPage, OrgUsersPage } from '@/pages/lazy'

// Shared by the browser router (main.tsx) and the memory router in tests.
export const appRoutes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <Navigate to="/me" replace /> },
          { path: 'me', element: <MyOverviewPage /> },
          { path: 'me/sessions', element: <MySessionsPage /> },
          { path: 'me/activity', element: <MyActivityPage /> },
          {
            path: 'org',
            element: <RequireOrganizationAccess />,
            children: [
              { index: true, element: <OrganizationOverviewPage /> },
              { path: 'events', element: <OrgEventsPage /> },
              { path: 'audit', element: <OrgAuditPage /> },
              { path: 'users', element: <OrgUsersPage /> },
              { path: 'users/:userId', element: <OrgUserPage /> },
            ],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]
