import type { ReactNode } from 'react'
import { useLocation } from 'react-router'

import { useCurrentUser } from '@/features/auth/hooks'
import { OrganizationPicker } from '@/features/org/OrganizationPicker'
import { cn } from '@/lib/utils'

import { scopeOf } from './navigation'

interface PageHeaderProps {
  title: ReactNode
  description?: ReactNode
  // Buttons on the right, such as Refresh.
  actions?: ReactNode
  className?: string
}

/** Every page's title, what it shows, and on the right its filters and
 * actions. The platform owner picks the organization here, on every
 * organization page. */
export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  const { pathname } = useLocation()
  const { data: user } = useCurrentUser()
  // The organizations page lists them all already; there is nothing to pick.
  const picker =
    user?.role === 'owner' && scopeOf(pathname) === 'organization' && pathname !== '/org/organizations'

  return (
    <header className={cn('flex flex-wrap items-start justify-between gap-x-6 gap-y-3', className)}>
      <div className="flex min-w-0 flex-col gap-1">
        <h1 className="text-2xl leading-tight font-semibold text-balance">{title}</h1>
        {description && <div className="max-w-prose text-muted-foreground">{description}</div>}
      </div>
      {(picker || actions) && (
        <div className="flex flex-wrap items-start gap-2">
          {picker && <OrganizationPicker />}
          {actions}
        </div>
      )}
    </header>
  )
}
