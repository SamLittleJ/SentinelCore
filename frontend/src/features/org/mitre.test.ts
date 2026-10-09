import { describe, expect, it } from 'vitest'

import { techniqueName, techniqueUrl } from './mitre'

describe('MITRE ATT&CK techniques', () => {
  it('links techniques and sub-techniques to their pages', () => {
    expect(techniqueUrl('T1078')).toBe('https://attack.mitre.org/techniques/T1078/')
    expect(techniqueUrl('T1110.003')).toBe('https://attack.mitre.org/techniques/T1110/003/')
  })

  it('builds no link from anything but a technique id', () => {
    for (const value of ['', 'T1078/../../evil', 'javascript:alert(1)', 'T10', 't1078', 'T1110.3']) {
      expect(techniqueUrl(value)).toBeUndefined()
    }
  })

  it('names the techniques the rules detect', () => {
    expect(techniqueName('T1110.003')).toBe('Brute Force: Password Spraying')
    expect(techniqueName('T9999')).toBeUndefined()
  })
})
