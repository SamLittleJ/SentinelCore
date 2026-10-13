import { createContext, useContext } from 'react'

// The address keeps the owner's choice, so a link opens the same view:
// `org=3` for one organization, `org=all` for every one.
export const ORGANIZATION_PARAM = 'org'
const ALL = 'all'

// What the address can say: one organization, or all of them.
export type OrganizationChoice = number | typeof ALL

export interface OrganizationView {
  // The organization the platform owner is looking at, or null for all.
  // Always null for everyone else: the API shows them their own.
  organizationId: number | null
  choose: (organizationId: number | null) => void
}

export const OrganizationViewContext = createContext<OrganizationView>({
  organizationId: null,
  choose: () => undefined,
})

/** The choice the address `search` holds; null when it holds none, or one
 * that is not valid. */
export function readOrganization(search: string): OrganizationChoice | null {
  const value = new URLSearchParams(search).get(ORGANIZATION_PARAM)
  if (value === ALL) return ALL
  return value !== null && /^[1-9]\d*$/.test(value) ? Number(value) : null
}

/** The address `search` holding `choice`. */
export function withOrganization(search: string, choice: OrganizationChoice): string {
  const params = new URLSearchParams(search)
  params.set(ORGANIZATION_PARAM, String(choice))
  return `?${params.toString()}`
}

export function choiceOf(organizationId: number | null): OrganizationChoice {
  return organizationId ?? ALL
}

export function organizationOf(choice: OrganizationChoice): number | null {
  return choice === ALL ? null : choice
}

export function useOrganizationView(): OrganizationView {
  return useContext(OrganizationViewContext)
}

/** The organization the pages show; null for all of them, or the reader's own. */
export function useViewedOrganization(): number | null {
  return useOrganizationView().organizationId
}
