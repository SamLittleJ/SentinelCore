import type { ReactNode } from 'react'

import { Wordmark } from '@/components/brand/Logomark'

/** The narrow, centered frame of the pages reached without an account:
 * signing in and accepting an invitation. */
export function PublicShell({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="flex flex-col gap-1.5">
          <Wordmark />
          <h1 className="mt-4 text-2xl font-semibold text-balance">{title}</h1>
          <p className="text-muted-foreground">{subtitle}</p>
        </div>
        {children}
      </div>
    </main>
  )
}
