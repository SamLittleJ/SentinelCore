import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'

import i18n from '@/i18n'

import { server } from './server'

// jsdom has no matchMedia; the theme provider needs it.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
})

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

beforeEach(async () => {
  localStorage.clear()
  document.documentElement.className = ''
  await i18n.changeLanguage('ro')
})

afterEach(() => {
  cleanup()
  server.resetHandlers()
  // Expire every cookie set during the test.
  for (const cookie of document.cookie.split(';')) {
    const name = cookie.split('=')[0].trim()
    if (name) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
    }
  }
})

afterAll(() => server.close())
