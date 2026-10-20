import { describe, expect, it } from 'vitest'

import { productionHeaders } from '../security-headers.ts'
import { nginxHeaders } from './nginx-headers.ts'

describe('nginx headers', () => {
  it('writes every production header, always sent, with its exact value', () => {
    const lines = nginxHeaders(productionHeaders).trimEnd().split('\n')

    expect(lines).toHaveLength(Object.keys(productionHeaders).length)
    for (const [name, value] of Object.entries(productionHeaders)) {
      expect(lines).toContain(`add_header ${name} "${value}" always;`)
    }
  })

  it('sends the production policy, not the development one', () => {
    const conf = nginxHeaders(productionHeaders)

    expect(conf).toContain("script-src 'self';")
    expect(conf).not.toContain("script-src 'self' 'unsafe-inline'")
    expect(conf).not.toContain('ws:')
  })

  it.each([
    ['a quote', 'a"b'],
    ['a variable', '$host'],
    ['a backslash', 'a\\b'],
    ['a new line', 'a\nb'],
  ])('refuses a value with %s', (_, value) => {
    expect(() => nginxHeaders({ 'X-Test': value })).toThrow('X-Test')
  })

  it('refuses a name nginx would split', () => {
    expect(() => nginxHeaders({ 'X Test': 'value' })).toThrow()
  })
})
