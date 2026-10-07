import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './locales/en'
import ro from './locales/ro'

export const LANGUAGES = ['ro', 'en'] as const
export type Language = (typeof LANGUAGES)[number]

const STORAGE_KEY = 'sentinelcore.language'
const DEFAULT_LANGUAGE: Language = 'ro'

function storedLanguage(): Language {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return LANGUAGES.includes(value as Language) ? (value as Language) : DEFAULT_LANGUAGE
  } catch {
    // Storage can be unavailable (private mode, blocked site data).
    return DEFAULT_LANGUAGE
  }
}

export const resources = {
  ro: { translation: ro },
  en: { translation: en },
} as const

void i18n.use(initReactI18next).init({
  resources,
  lng: storedLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  supportedLngs: LANGUAGES,
  // React already escapes rendered text.
  interpolation: { escapeValue: false },
})

document.documentElement.lang = i18n.language

i18n.on('languageChanged', (language) => {
  document.documentElement.lang = language
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // The choice still applies for this visit.
  }
})

export default i18n
