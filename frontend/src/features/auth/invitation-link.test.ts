import { describe, expect, it } from 'vitest'

import { invitationLink, tokenFromHash } from '@/features/auth/invitation-link'

describe('invitation links', () => {
  it('carry the token in the fragment, never in the path or query', () => {
    const link = new URL(invitationLink('sci_abc_def', 'https://sentinel.example'))
    expect(link.pathname).toBe('/invite')
    expect(link.search).toBe('')
    expect(link.hash).toBe('#sci_abc_def')
  })

  it('read the token back, or nothing from an empty fragment', () => {
    expect(tokenFromHash('#sci_abc_def')).toBe('sci_abc_def')
    expect(tokenFromHash('#')).toBeNull()
    expect(tokenFromHash('')).toBeNull()
  })
})
