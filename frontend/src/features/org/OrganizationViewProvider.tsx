import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'

import { scopeOf } from '@/components/layout/navigation'

import {
  choiceOf,
  type OrganizationChoice,
  OrganizationViewContext,
  organizationOf,
  readOrganization,
  withOrganization,
} from './organization-view'

/**
 * Holds the platform owner's choice of organization for every organization
 * page at once. The address is where the choice lives: choosing writes it
 * there, always explicitly. Pages rewrite their address with each filter,
 * though, and links inside the pages do not carry it; so the last choice
 * seen is also remembered here, read while the address holds none, and put
 * back. Queries therefore never load every organization in between, which
 * matters because each such load is audited.
 */
export function OrganizationViewProvider({
  enabled,
  children,
}: {
  enabled: boolean
  children: ReactNode
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const inOrganization = scopeOf(location.pathname) === 'organization'
  const fromAddress = enabled && inOrganization ? readOrganization(location.search) : null
  const [remembered, setRemembered] = useState<OrganizationChoice>(
    () => readOrganization(location.search) ?? 'all',
  )

  // The address wins, as after a choice, Back or an opened link. It is
  // remembered during this render, so nothing reads the previous one.
  if (fromAddress !== null && fromAddress !== remembered) {
    setRemembered(fromAddress)
  }
  const organizationId = enabled ? organizationOf(fromAddress ?? remembered) : null

  // A step that dropped a single organization from the address puts it
  // back, so the address still says what the page shows.
  useEffect(() => {
    if (enabled && inOrganization && fromAddress === null && remembered !== 'all') {
      void navigate(
        { pathname: location.pathname, search: withOrganization(location.search, remembered) },
        { replace: true, state: location.state },
      )
    }
  }, [enabled, inOrganization, fromAddress, remembered, location, navigate])

  const choose = useCallback(
    (next: number | null) =>
      void navigate({
        pathname: location.pathname,
        search: withOrganization(location.search, choiceOf(next)),
      }),
    [location.pathname, location.search, navigate],
  )

  const value = useMemo(() => ({ organizationId, choose }), [organizationId, choose])
  return <OrganizationViewContext value={value}>{children}</OrganizationViewContext>
}
