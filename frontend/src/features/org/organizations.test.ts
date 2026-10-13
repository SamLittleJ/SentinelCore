import { describe, expect, it } from 'vitest'

import { slugFrom, validOrganizationName, validSlug } from './organizations'

describe('slugFrom', () => {
  it('lowercases and joins words with hyphens', () => {
    expect(slugFrom('Globex Europa')).toBe('globex-europa')
  })

  it('drops diacritics and symbols, and hyphens at the ends', () => {
    expect(slugFrom('  Ștefan & Fiii!  ')).toBe('stefan-fiii')
  })

  it('suggests a slug the API accepts, cut to its length', () => {
    const slug = slugFrom('A'.repeat(39) + ' B')
    expect(slug).toBe('a'.repeat(39))
    expect(validSlug(slug)).toBe(true)
  })
})

describe('validSlug', () => {
  it.each(['acme', 'globex-eu', 'a1'])('accepts %s', (slug) => {
    expect(validSlug(slug)).toBe(true)
  })

  it.each(['a', 'Acme', 'acme-', '-acme', 'ac--me', 'ac me', 'a'.repeat(41)])(
    'refuses %s',
    (slug) => {
      expect(validSlug(slug)).toBe(false)
    },
  )
})

describe('validOrganizationName', () => {
  it('counts the name without surrounding spaces', () => {
    expect(validOrganizationName(' A ')).toBe(false)
    expect(validOrganizationName('Ab')).toBe(true)
    expect(validOrganizationName('x'.repeat(101))).toBe(false)
  })
})
