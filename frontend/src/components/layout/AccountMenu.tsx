import { ChevronsUpDown, LogOut } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { User } from '@/features/auth/api'
import { useLogOut } from '@/features/auth/hooks'
import { THEMES, useTheme, type Theme } from '@/features/theme/theme-context'
import { LANGUAGES, type Language } from '@/i18n'

const THEME_LABEL_KEYS = {
  dark: 'account.themeDark',
  light: 'account.themeLight',
  system: 'account.themeSystem',
} as const

const LANGUAGE_NAMES: Record<Language, string> = { ro: 'Română', en: 'English' }

export function AccountMenu({ user }: { user: User }) {
  const { t, i18n } = useTranslation()
  const { theme, setTheme } = useTheme()
  const logOut = useLogOut()
  const navigate = useNavigate()

  const handleLogOut = () => {
    logOut.mutate(undefined, {
      onSettled: () => void navigate('/login', { replace: true }),
    })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex w-full items-center justify-between gap-2 rounded-md px-2 py-2 text-left hover:bg-sidebar-accent/60 focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none"
        aria-label={t('account.menu')}
      >
        <span className="flex min-w-0 flex-col">
          <span className="truncate font-medium">{user.username}</span>
          <span className="truncate font-mono text-xs text-muted-foreground">
            {t(`roles.${user.role}`)}
          </span>
        </span>
        <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="w-56">
        <DropdownMenuLabel className="truncate font-normal text-muted-foreground">
          {user.email}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>{t('account.theme')}</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={theme} onValueChange={(value) => setTheme(value as Theme)}>
          {THEMES.map((option) => (
            <DropdownMenuRadioItem key={option} value={option}>
              {t(THEME_LABEL_KEYS[option])}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>{t('account.language')}</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={i18n.language}
          onValueChange={(value) => void i18n.changeLanguage(value)}
        >
          {LANGUAGES.map((language) => (
            <DropdownMenuRadioItem key={language} value={language} lang={language}>
              {LANGUAGE_NAMES[language]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={handleLogOut} disabled={logOut.isPending}>
          <LogOut aria-hidden />
          {t('account.logout')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
