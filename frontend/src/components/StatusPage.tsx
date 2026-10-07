import type { ReactNode } from 'react'

interface StatusPageProps {
  title: string
  body: string
  action?: ReactNode
  fullScreen?: boolean
}

/** Loading, error and empty states share one quiet layout. */
export function StatusPage({ title, body, action, fullScreen = false }: StatusPageProps) {
  return (
    <div
      className={
        fullScreen
          ? 'flex min-h-screen items-center justify-center px-4'
          : 'flex items-center justify-center px-4 py-24'
      }
    >
      <div className="flex max-w-md flex-col items-start gap-3">
        <h1 className="text-lg font-semibold text-balance">{title}</h1>
        <p className="text-muted-foreground">{body}</p>
        {action}
      </div>
    </div>
  )
}

export function FullPageLoader({ label }: { label: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center" role="status">
      <span className="font-mono text-sm text-muted-foreground">{label}</span>
    </div>
  )
}
