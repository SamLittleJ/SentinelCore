import { useTranslation } from 'react-i18next'
import { Link, Navigate, Outlet, useLocation } from 'react-router'

import { FullPageLoader, StatusPage } from '@/components/StatusPage'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/api'

import { canViewOrganization, isAccountLockedError } from './api'
import { isUnauthenticated, useCurrentUser } from './hooks'

/** Renders the protected routes only for a signed-in, active user. */
export function RequireAuth() {
  const { t } = useTranslation()
  const location = useLocation()
  const currentUser = useCurrentUser()

  if (currentUser.isPending) {
    return <FullPageLoader label={t('app.loading')} />
  }

  if (currentUser.isError) {
    if (isUnauthenticated(currentUser.error)) {
      const next = encodeURIComponent(location.pathname + location.search)
      return <Navigate to={`/login?next=${next}`} replace />
    }
    if (isAccountLockedError(currentUser.error)) {
      return <Navigate to="/login?reason=locked" replace />
    }
    if (currentUser.error instanceof ApiError && currentUser.error.status === 403) {
      return <Navigate to="/login?reason=inactive" replace />
    }
    return (
      <StatusPage
        fullScreen
        title={t('errors.loadFailedTitle')}
        body={t('errors.loadFailedBody')}
        action={<Button onClick={() => void currentUser.refetch()}>{t('errors.retry')}</Button>}
      />
    )
  }

  return <Outlet />
}

/**
 * The API enforces roles on every organization endpoint; this guard only
 * avoids showing pages whose requests would all be refused.
 */
export function RequireOrganizationAccess() {
  const { t } = useTranslation()
  const { data: user } = useCurrentUser()

  if (user === undefined || !canViewOrganization(user)) {
    return (
      <StatusPage
        title={t('errors.forbiddenTitle')}
        body={t('errors.forbiddenBody')}
        action={
          <Button asChild variant="outline">
            <Link to="/me">{t('errors.backToAccount')}</Link>
          </Button>
        }
      />
    )
  }

  return <Outlet />
}
