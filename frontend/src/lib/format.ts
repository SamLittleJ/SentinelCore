import { useTranslation } from 'react-i18next'

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

export function formatDate(value: string | Date, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(new Date(value))
}

export function formatDateTime(value: string | Date, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  )
}

/**
 * "acum 5 minute" / "peste 2 ore". Past a month the exact date is clearer
 * than "acum 7 săptămâni".
 */
export function formatRelative(value: string | Date, locale: string, now = Date.now()): string {
  const diff = new Date(value).getTime() - now
  const distance = Math.abs(diff)
  const relative = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })

  if (distance < MINUTE) {
    return relative.format(0, 'second')
  }
  if (distance < HOUR) {
    return relative.format(Math.round(diff / MINUTE), 'minute')
  }
  if (distance < DAY) {
    return relative.format(Math.round(diff / HOUR), 'hour')
  }
  if (distance < 30 * DAY) {
    return relative.format(Math.round(diff / DAY), 'day')
  }
  return formatDate(value, locale)
}

/** Date formatters bound to the interface language. */
export function useFormatters() {
  const { i18n } = useTranslation()
  const locale = i18n.language
  return {
    date: (value: string | Date) => formatDate(value, locale),
    dateTime: (value: string | Date) => formatDateTime(value, locale),
    relative: (value: string | Date) => formatRelative(value, locale),
  }
}
