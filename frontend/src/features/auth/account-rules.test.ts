import { describe, expect, it } from 'vitest'

import { validNewPassword, validUsername } from '@/features/auth/api'

describe('new account rules, as the API applies them', () => {
  it('takes usernames of 3 to 50 letters, digits and "_ . -"', () => {
    expect(validUsername('dana.ilie')).toBe(true)
    expect(validUsername('Dana_I-1')).toBe(true)
    expect(validUsername('ab')).toBe(false)
    expect(validUsername('a'.repeat(51))).toBe(false)
    expect(validUsername('dana ilie')).toBe(false)
    expect(validUsername('dana@ilie')).toBe(false)
  })

  it('takes passwords of 12 to 128 characters, counted by code point', () => {
    expect(validNewPassword('a'.repeat(11))).toBe(false)
    expect(validNewPassword('a'.repeat(12))).toBe(true)
    expect(validNewPassword('a'.repeat(128))).toBe(true)
    expect(validNewPassword('a'.repeat(129))).toBe(false)
    // Six emoji are twelve UTF-16 units but six characters for the API.
    expect(validNewPassword('🔐'.repeat(6))).toBe(false)
    expect(validNewPassword('🔐'.repeat(12))).toBe(true)
  })
})
