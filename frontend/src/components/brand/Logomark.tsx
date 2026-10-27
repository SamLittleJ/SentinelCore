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

/** The mark and the name, read once by screen readers. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn('flex items-center gap-2', className)}>
      <Logomark className="size-6 text-brand" />
      <span className="text-[15px] font-semibold">SentinelCore</span>
    </span>
  )
}
