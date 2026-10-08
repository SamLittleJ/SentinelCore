import { Search, X } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface SearchFormProps {
  label: string
  submitLabel: string
  clearLabel: string
  value: string
  onSubmit: (search: string) => void
}

/** A search field that applies on Enter or the search button, not on every
 * keystroke, since every list load is audited. */
export function SearchForm({ label, submitLabel, clearLabel, value, onSubmit }: SearchFormProps) {
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
        {label}
      </label>
      <div className="relative flex-1">
        <Input
          id={inputId}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={label}
          className="pr-8 font-mono text-xs"
          autoComplete="off"
          spellCheck={false}
        />
        {draft && (
          <button
            type="button"
            aria-label={clearLabel}
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
      <Button type="submit" variant="outline" size="icon" aria-label={submitLabel}>
        <Search aria-hidden />
      </Button>
    </form>
  )
}
