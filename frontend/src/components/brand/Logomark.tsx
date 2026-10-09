import { cn } from '@/lib/utils'

/** The SentinelCore mark: a shield with a watching eye. Drawn in the current
 * text color, so it follows the theme. Decorative: the wordmark or the
 * surrounding label names the application. */
export function Logomark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinejoin="round"
      aria-hidden
      className={cn('size-8 shrink-0', className)}
    >
      <path d="M16 3 27 7v8c0 7-5 12-11 14C10 27 5 22 5 15V7Z" />
      <path d="M9 16c2.5-3.6 11.5-3.6 14 0-2.5 3.6-11.5 3.6-14 0Z" />
      <circle cx="16" cy="16" r="2.2" fill="currentColor" stroke="none" />
    </svg>
  )
}

/** "SENTINEL core": the condensed name and the mono suffix, read as one
 * word by screen readers. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn('flex items-center gap-2.5', className)}>
      <Logomark className="text-brand" />
      <span aria-label="SentinelCore" role="img" className="flex items-baseline gap-0.5">
        <span aria-hidden className="font-display text-lg font-bold tracking-[0.08em]">
          SENTINEL
        </span>
        <span aria-hidden className="font-mono text-sm font-medium text-brand">
          core
        </span>
      </span>
    </span>
  )
}
