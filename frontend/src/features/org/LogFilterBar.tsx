import { ChevronDown, Search, X } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { SegmentedControl } from '@/components/SegmentedControl'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { SEVERITIES, type Severity } from '@/features/account/api'
import { cn } from '@/lib/utils'

import {
  DEFAULT_RANGE,
  hasNarrowingFilters,
  type LogFilters,
  TIME_RANGES,
} from './filters'

interface LogFilterBarProps<Type extends string> {
  filters: LogFilters<Type>
  onChange: (filters: LogFilters<Type>) => void
  types: readonly Type[]
  typeLabel: (type: Type) => string
  // Only the security events log has severities.
  withSeverity?: boolean
}

function toggle<T>(values: readonly T[], value: T): T[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value]
}

export function LogFilterBar<Type extends string>({
  filters,
  onChange,
  types,
  typeLabel,
  withSeverity = false,
}: LogFilterBarProps<Type>) {
  const { t } = useTranslation()
  const update = (changes: Partial<LogFilters<Type>>) => onChange({ ...filters, ...changes })

  const rangeOptions = TIME_RANGES.map((range) => ({ value: range, label: t(`orgLog.range.${range}`) }))
  const canReset = hasNarrowingFilters(filters) || filters.range !== DEFAULT_RANGE

  return (
    <section aria-label={t('orgLog.filtersLabel')} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl
          label={t('orgLog.rangeLabel')}
          options={rangeOptions}
          value={filters.range}
          onChange={(range) => update({ range })}
        />

        {withSeverity && (
          <SeverityToggles
            selected={filters.severities}
            onToggle={(severity) => update({ severities: toggle(filters.severities, severity) })}
          />
        )}

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" aria-label={t('orgLog.typesLabel')}>
              {filters.types.length === 0
                ? t('orgLog.typesAll')
                : t('orgLog.typesSome', { count: filters.types.length })}
              <ChevronDown aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="max-h-80">
            <DropdownMenuItem disabled={filters.types.length === 0} onSelect={() => update({ types: [] })}>
              {t('orgLog.typesAll')}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {types.map((type) => (
              <DropdownMenuCheckboxItem
                key={type}
                checked={filters.types.includes(type)}
                // Keeps the menu open, so several types can be picked at once.
                onSelect={(event) => event.preventDefault()}
                onCheckedChange={() => update({ types: toggle(filters.types, type) })}
              >
                {typeLabel(type)}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <SearchForm value={filters.search} onSubmit={(search) => update({ search })} />

        {filters.userId !== undefined && (
          <FilterChip
            label={t('orgLog.accountFilter', { id: filters.userId })}
            onRemove={() => update({ userId: undefined })}
          />
        )}
        {filters.targetUserId !== undefined && (
          <FilterChip
            label={t('orgLog.targetFilter', { id: filters.targetUserId })}
            onRemove={() => update({ targetUserId: undefined })}
          />
        )}

        {canReset && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              onChange({ range: DEFAULT_RANGE, types: [], severities: [], search: '' })
            }
          >
            {t('orgLog.reset')}
          </Button>
        )}
      </div>
    </section>
  )
}

function SeverityToggles({
  selected,
  onToggle,
}: {
  selected: readonly Severity[]
  onToggle: (severity: Severity) => void
}) {
  const { t } = useTranslation()
  return (
    <div role="group" aria-label={t('orgLog.severityLabel')} className="inline-flex gap-1 rounded-lg border bg-card p-1">
      {SEVERITIES.map((severity) => {
        const pressed = selected.includes(severity)
        return (
          <button
            key={severity}
            type="button"
            aria-pressed={pressed}
            onClick={() => onToggle(severity)}
            className={cn(
              'rounded-md px-3 py-1 text-sm transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
              pressed
                ? {
                    info: 'bg-sev-info-bg font-medium text-sev-info',
                    warn: 'bg-sev-warn-bg font-medium text-sev-warn',
                    incident: 'bg-sev-incident-bg font-medium text-sev-incident',
                  }[severity]
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {t(`severity.${severity}`)}
          </button>
        )
      })}
    </div>
  )
}

function SearchForm({ value, onSubmit }: { value: string; onSubmit: (search: string) => void }) {
  const { t } = useTranslation()
  const inputId = useId()
  const [draft, setDraft] = useState(value)
  // Follows changes made elsewhere, e.g. from a record's details or a reset,
  // without remounting, so the field keeps focus after a search.
  const [shown, setShown] = useState(value)
  if (value !== shown) {
    setShown(value)
    setDraft(value)
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmit(draft.trim())
  }

  return (
    <form role="search" onSubmit={handleSubmit} className="flex w-full max-w-sm items-center gap-2">
      <label htmlFor={inputId} className="sr-only">
        {t('orgLog.search')}
      </label>
      <div className="relative flex-1">
        <Input
          id={inputId}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={t('orgLog.search')}
          className="pr-8 font-mono text-xs"
          autoComplete="off"
          spellCheck={false}
        />
        {draft && (
          <button
            type="button"
            aria-label={t('orgLog.clearSearch')}
            onClick={() => {
              setDraft('')
              if (value) onSubmit('')
            }}
            className="absolute top-1/2 right-2 -translate-y-1/2 rounded-sm text-muted-foreground hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            <X aria-hidden className="size-4" />
          </button>
        )}
      </div>
      <Button type="submit" variant="outline" size="icon" aria-label={t('orgLog.searchSubmit')}>
        <Search aria-hidden />
      </Button>
    </form>
  )
}

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex items-center gap-1 rounded-md border bg-card py-1 pr-1 pl-2.5 font-mono text-xs">
      {label}
      <button
        type="button"
        aria-label={t('orgLog.removeFilter', { name: label })}
        onClick={onRemove}
        className="rounded-sm p-0.5 text-muted-foreground hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <X aria-hidden className="size-3.5" />
      </button>
    </span>
  )
}
