import 'i18next'

import type ro from './locales/ro'

// Translation keys are checked at compile time against the Romanian resources.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation'
    resources: {
      translation: typeof ro
    }
  }
}
