import { CornerDownLeft, Search } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { type KeyboardEvent, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { canViewOrganization, type User } from '@/features/auth/api'
import { useLogOut } from '@/features/auth/hooks'
import { DEFAULT_RANGE, writeLogFilters } from '@/features/org/filters'
import { writeUserFilters } from '@/features/org/user-filters'
import { THEMES, useTheme } from '@/features/theme/theme-context'
import { LANGUAGES } from '@/i18n'
import { cn } from '@/lib/utils'

import { NAV } from './navigation'

type Group = 'search' | 'pages' | 'actions'

interface Command {
  id: string
  group: Group
  label: string
  // Shown on the right, e.g. where a page sits.
  hint?: string
  run: () => void
}

const GROUP_ORDER: Group[] = ['search', 'pages', 'actions']

const THEME_LABEL_KEYS = {
  dark: 'palette.themeDark',
  light: 'palette.themeLight',
  system: 'palette.themeSystem',
} as const

const LANGUAGE_LABEL_KEYS = { ro: 'palette.languageRo', en: 'palette.languageEn' } as const

/** Lowercase and without diacritics, so "activitate" finds "Activitatea"
 * and "sesiuni" finds "Sesiunile". */
function normalize(text: string): string {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}

/** Everything the palette can do for `user`. Searching opens the filtered
 * page, which loads (and audits) the records as usual: the palette itself
 * never asks the API for anything. */
function useCommands(user: User, query: string, close: () => void): Command[] {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { theme, setTheme } = useTheme()
  const logOut = useLogOut()

  const go = (to: string) => () => {
    close()
    void navigate(to)
  }
  const operator = canViewOrganization(user)
  const text = query.trim()
  const commands: Command[] = []

  if (text && operator) {
    commands.push(
      {
        id: 'search-users',
        group: 'search',
        label: t('palette.searchUsers', { query: text }),
        run: go(`/org/users?${writeUserFilters({ search: text, roles: [] }).toString()}`),
      },
      {
        id: 'search-events',
        group: 'search',
        label: t('palette.searchEvents', { query: text }),
        hint: t('palette.searchEventsHint'),
        run: go(
          `/org/events?${writeLogFilters({ range: DEFAULT_RANGE, types: [], severities: [], search: text }).toString()}`,
        ),
      },
    )
  }

  const scopes = operator ? (['personal', 'organization'] as const) : (['personal'] as const)
  for (const scope of scopes) {
    for (const item of NAV[scope]) {
      commands.push({
        id: `page-${item.to}`,
        group: 'pages',
        label: t(item.label),
        hint: `${t(`scope.${scope}`)} / ${item.number}`,
        run: go(item.to),
      })
    }
  }

  for (const option of THEMES) {
    commands.push({
      id: `theme-${option}`,
      group: 'actions',
      label: t(THEME_LABEL_KEYS[option]),
      hint: option === theme ? t('palette.current') : undefined,
      run: () => {
        setTheme(option)
        close()
      },
    })
  }
  for (const language of LANGUAGES) {
    commands.push({
      id: `language-${language}`,
      group: 'actions',
      label: t(LANGUAGE_LABEL_KEYS[language]),
      hint: language === i18n.language ? t('palette.current') : undefined,
      run: () => {
        void i18n.changeLanguage(language)
        close()
      },
    })
  }
  commands.push({
    id: 'logout',
    group: 'actions',
    label: t('account.logout'),
    run: () => {
      close()
      logOut.mutate(undefined, { onSettled: () => void navigate('/login', { replace: true }) })
    },
  })

  if (!text) return commands
  const wanted = normalize(text)
  return commands.filter(
    (command) => command.group === 'search' || normalize(`${command.label} ${command.hint ?? ''}`).includes(wanted),
  )
}

interface CommandPaletteProps {
  user: User
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Ctrl+K: jump to a page, search the organization, or change a setting,
 * from the keyboard. An ARIA combobox: focus stays in the input, the arrow
 * keys move through the list, Enter runs the highlighted command. */
export function CommandPalette({ user, open, onOpenChange }: CommandPaletteProps) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const listId = useId()

  const setOpen = (next: boolean) => {
    if (!next) {
      setQuery('')
      setActive(0)
    }
    onOpenChange(next)
  }
  const close = () => setOpen(false)
  const commands = useCommands(user, query, close)
  const groups = GROUP_ORDER.map((group) => ({
    group,
    items: commands.filter((command) => command.group === group),
  })).filter(({ items }) => items.length > 0)
  // The list in the order it is shown, which the arrow keys follow.
  const ordered = groups.flatMap(({ items }) => items)
  const current = Math.min(active, Math.max(ordered.length - 1, 0))
  const optionId = (index: number) => `${listId}-${index}`

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (ordered.length === 0) return
      const step = event.key === 'ArrowDown' ? 1 : -1
      setActive((current + step + ordered.length) % ordered.length)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      ordered[current]?.run()
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[12vh] left-1/2 z-50 flex max-h-[70vh] w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 flex-col overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-2xl"
        >
          <Dialog.Title className="sr-only">{t('palette.title')}</Dialog.Title>
          <div className="flex items-center gap-3 border-b px-4">
            <Search aria-hidden className="size-4 shrink-0 text-brand" />
            <input
              role="combobox"
              aria-expanded
              aria-controls={listId}
              aria-activedescendant={ordered.length > 0 ? optionId(current) : undefined}
              aria-autocomplete="list"
              aria-label={t('palette.input')}
              placeholder={t('palette.placeholder')}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                setActive(0)
              }}
              onKeyDown={onKeyDown}
              className="h-14 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
            />
            <kbd className="label-mono rounded border px-1.5 py-0.5 tracking-normal text-muted-foreground normal-case">Esc</kbd>
          </div>

          <div id={listId} role="listbox" aria-label={t('palette.results')} className="overflow-y-auto p-2">
            {ordered.length === 0 && (
              <p className="px-3 py-6 text-center text-muted-foreground">{t('palette.empty')}</p>
            )}
            {groups.map(({ group, items }) => (
              <div key={group} role="group" aria-labelledby={`${listId}-${group}`} className="flex flex-col gap-0.5 pb-1">
                <span id={`${listId}-${group}`} className="label-mono px-3 pt-2 pb-1 text-muted-foreground">
                  {t(`palette.groups.${group}`)}
                </span>
                {items.map((command) => {
                  const index = ordered.indexOf(command)
                  const selected = index === current
                  return (
                    <div
                      key={command.id}
                      id={optionId(index)}
                      role="option"
                      aria-selected={selected}
                      // The input keeps focus; a click on an option runs it.
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={command.run}
                      onMouseMove={() => setActive(index)}
                      className={cn(
                        'flex min-h-10 cursor-pointer items-center gap-3 rounded-md px-3 py-2',
                        selected && 'bg-brand-tint text-foreground',
                      )}
                    >
                      <span className="min-w-0 flex-1 truncate">{command.label}</span>
                      {command.hint && (
                        <span className="label-mono shrink-0 tracking-normal text-muted-foreground normal-case">
                          {command.hint}
                        </span>
                      )}
                      {selected && <CornerDownLeft aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>

          <p className="label-mono flex gap-4 border-t px-4 py-2 tracking-normal text-muted-foreground normal-case">
            <span>{t('palette.keysMove')}</span>
            <span>{t('palette.keysRun')}</span>
            <span>{t('palette.keysClose')}</span>
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
