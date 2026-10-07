import { cn } from '@/lib/utils'

interface SegmentedControlProps<Value extends string> {
  label: string
  options: readonly { value: Value; label: string }[]
  value: Value
  onChange: (value: Value) => void
}

/** A row of mutually exclusive filter buttons; the chosen one is pressed. */
export function SegmentedControl<Value extends string>({
  label,
  options,
  value,
  onChange,
}: SegmentedControlProps<Value>) {
  return (
    <div
      role="group"
      aria-label={label}
      // Wraps on narrow screens, so every option stays visible.
      className="inline-flex w-fit max-w-full flex-wrap gap-1 rounded-lg border bg-card p-1"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            'rounded-md px-3 py-1 text-sm whitespace-nowrap transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
            value === option.value
              ? 'bg-brand-tint font-medium text-brand'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
