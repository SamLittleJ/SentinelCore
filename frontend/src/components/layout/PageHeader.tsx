import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router'

import { cn } from '@/lib/utils'

import { navItemFor, scopeOf } from './navigation'

interface PageHeaderProps {
  title: ReactNode
  description?: ReactNode
  // Buttons on the right, such as Refresh.
  actions?: ReactNode
  className?: string
}

/** Every page's title block: where the page sits ("ORGANIZAȚIA / 02
 * EVENIMENTE DE SECURITATE"), its title and what it shows. */
export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const scope = scopeOf(pathname)
  const item = navItemFor(pathname)

  return (
    <header className={cn('flex flex-wrap items-end justify-between gap-4', className)}>
      <div className="flex min-w-0 flex-col gap-2">
        <p className="label-mono text-brand">
          {t(`scope.${scope}`)}
          {item && (
            <>
              {' / '}
              {item.number} {t(item.label)}
            </>
          )}
        </p>
        <h1 className="font-display text-3xl leading-tight font-semibold text-balance md:text-4xl">
          {title}
        </h1>
        {description && <div className="max-w-prose text-muted-foreground">{description}</div>}
      </div>
      {actions}
    </header>
  )
}
