import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { Role } from '@/features/auth/api'
import type { ApiKey } from '@/features/org/api'
import { renderApp } from '@/test/render'
import { makeApiKey, makeUser, server, signedInAs } from '@/test/server'

const DAY = 24 * 3600_000
// Not a real key: the shape the API answers with.
const FULL_KEY = `sck_n3wk3y01_${'example'.repeat(6)}`

const vpn = makeApiKey({
  id: 3,
  name: 'Corporate VPN',
  source: 'vpn',
  prefix: 'a1b2c3d4',
  last_used_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
})
const oldIdp = makeApiKey({
  id: 2,
  name: 'Old identity provider',
  source: 'idp',
  prefix: 'e5f6a7b8',
  expires_at: new Date(Date.now() - DAY).toISOString(),
})
const cluster = makeApiKey({
  id: 1,
  name: 'Cluster audit',
  source: 'k8s-audit',
  prefix: 'c9d0e1f2',
  revoked_at: new Date(Date.now() - 3 * DAY).toISOString(),
})

/** Answers the key list with `keys()` at each request, and counts them. */
function serveKeys(keys: () => ApiKey[]) {
  const requests = { count: 0 }
  server.use(
    http.get('/api/admin/api-keys', () => {
      requests.count += 1
      return HttpResponse.json(keys())
    }),
  )
  return requests
}

async function openKeys(role: Role) {
  signedInAs(makeUser(role, { id: 1 }))
  const result = renderApp('/org/api-keys')
  const table = await screen.findByRole('table', { name: 'Chei API' })
  return { ...result, table }
}

function rows(table: HTMLElement) {
  return within(table).getAllByRole('row').slice(1)
}

describe('organization API keys page', () => {
  it.each(['admin', 'security_analyst'] as const)(
    'shows every key to a %s, who cannot change them',
    async (role) => {
      serveKeys(() => [vpn, oldIdp, cluster])
      const { table } = await openKeys(role)

      const [first, second, third] = rows(table)
      expect(first).toHaveTextContent('Corporate VPN')
      expect(first).toHaveTextContent('sck_a1b2c3d4_…')
      expect(first).toHaveTextContent('vpn')
      expect(first).toHaveTextContent('Activă')
      expect(first).toHaveTextContent('acum 2 ore')
      expect(second).toHaveTextContent('Expirată')
      expect(second).toHaveTextContent('Niciodată')
      expect(third).toHaveTextContent('Revocată')
      expect(third).toHaveTextContent('k8s-audit')

      expect(screen.getByText('Doar owner-ul organizației creează și revocă chei.')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Cheie nouă' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Revocă/ })).not.toBeInTheDocument()
    },
  )

  it('lets the owner create a key, shows it once, and keeps it nowhere else', async () => {
    const user = userEvent.setup()
    const created = makeApiKey({ id: 4, name: 'Okta', source: 'okta', prefix: 'n3wk3y01' })
    let keys = [vpn]
    const listed = serveKeys(() => keys)
    const bodies: unknown[] = []
    server.use(
      http.post('/api/admin/api-keys', async ({ request }) => {
        bodies.push(await request.json())
        keys = [created, vpn]
        return HttpResponse.json({ api_key: created, key: FULL_KEY }, { status: 201 })
      }),
    )
    const { router, queryClient } = await openKeys('owner')

    await user.click(screen.getByRole('button', { name: 'Cheie nouă' }))
    const form = screen.getByRole('form', { name: 'Creează o cheie API' })
    await user.type(within(form).getByLabelText('Nume'), '  Okta  ')
    await user.type(within(form).getByLabelText('Sursă'), 'Okta')
    await user.click(within(form).getByRole('button', { name: '1 an' }))
    await user.click(within(form).getByRole('button', { name: 'Confirmă' }))

    const panel = await screen.findByRole('region', { name: 'Cheia „Okta” a fost creată' })
    expect(bodies).toEqual([{ name: 'Okta', source: 'okta', expires_in_days: 365 }])
    expect(panel).toHaveTextContent(FULL_KEY)
    expect(panel).toHaveTextContent('Nu va mai fi afișată')

    await user.click(within(panel).getByRole('button', { name: 'Copiază' }))
    expect(await navigator.clipboard.readText()).toBe(FULL_KEY)
    expect(within(panel).getByRole('status')).toHaveTextContent('Cheia a fost copiată.')

    // The list shows the new key by its prefix only.
    expect(listed.count).toBe(2)
    const table = screen.getByRole('table', { name: 'Chei API' })
    expect(rows(table)[0]).toHaveTextContent('sck_n3wk3y01_…')

    // The full key lives in the page's state, and nowhere that outlasts it.
    expect(router.state.location.pathname + router.state.location.search).not.toContain(FULL_KEY)
    expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain(FULL_KEY)
    expect(JSON.stringify(queryClient.getQueryCache().getAll().map((q) => q.state.data))).not.toContain(
      FULL_KEY,
    )
    expect(
      JSON.stringify(queryClient.getMutationCache().getAll().map((m) => m.state.data)),
    ).not.toContain(FULL_KEY)

    await user.click(within(panel).getByRole('button', { name: 'Am salvat cheia' }))
    expect(document.body).not.toHaveTextContent(FULL_KEY)
    expect(screen.getByRole('button', { name: 'Cheie nouă' })).toBeInTheDocument()
  })

  it('checks the name and source before sending them', async () => {
    const user = userEvent.setup()
    serveKeys(() => [vpn])
    await openKeys('owner')

    await user.click(screen.getByRole('button', { name: 'Cheie nouă' }))
    const form = screen.getByRole('form', { name: 'Creează o cheie API' })
    const confirm = within(form).getByRole('button', { name: 'Confirmă' })
    const source = within(form).getByLabelText('Sursă')

    await user.type(within(form).getByLabelText('Nume'), 'ab')
    await user.type(source, 'vpn')
    expect(confirm).toBeDisabled()

    await user.type(within(form).getByLabelText('Nume'), 'c')
    expect(confirm).toBeEnabled()

    await user.clear(source)
    await user.type(source, 'backend')
    expect(source).toHaveAttribute('aria-invalid', 'true')
    expect(form).toHaveTextContent('Sursele „backend” și „detection” sunt rezervate')
    expect(confirm).toBeDisabled()

    await user.clear(source)
    await user.type(source, '-vpn')
    expect(form).toHaveTextContent('Între 2 și 50 de caractere')
    expect(confirm).toBeDisabled()
  })

  it('explains a refused key and keeps the form', async () => {
    const user = userEvent.setup()
    serveKeys(() => [vpn])
    server.use(
      http.post('/api/admin/api-keys', () =>
        HttpResponse.json({ detail: [{ msg: 'invalid' }] }, { status: 422 }),
      ),
    )
    await openKeys('owner')

    await user.click(screen.getByRole('button', { name: 'Cheie nouă' }))
    const form = screen.getByRole('form', { name: 'Creează o cheie API' })
    await user.type(within(form).getByLabelText('Nume'), 'Okta')
    await user.type(within(form).getByLabelText('Sursă'), 'okta')
    await user.click(within(form).getByRole('button', { name: 'Confirmă' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('API-ul a refuzat datele cheii')
    expect(screen.getByRole('form', { name: 'Creează o cheie API' })).toBeInTheDocument()
  })

  it('revokes only active keys, after confirmation', async () => {
    const user = userEvent.setup()
    let keys = [vpn, oldIdp, cluster]
    const listed = serveKeys(() => keys)
    const revoked: string[] = []
    server.use(
      http.post('/api/admin/api-keys/:keyId/revoke', ({ params }) => {
        revoked.push(String(params.keyId))
        const after = { ...vpn, revoked_at: new Date().toISOString() }
        keys = [after, oldIdp, cluster]
        return HttpResponse.json(after)
      }),
    )
    const { table } = await openKeys('owner')

    // Expired and revoked keys offer nothing to revoke.
    const [first, second, third] = rows(table)
    expect(within(second).queryByRole('button')).not.toBeInTheDocument()
    expect(within(third).queryByRole('button')).not.toBeInTheDocument()

    await user.click(within(first).getByRole('button', { name: 'Revocă cheia Corporate VPN' }))
    let form = screen.getByRole('form', { name: 'Revocă cheia „Corporate VPN”' })
    expect(form).toHaveTextContent('nu poate fi anulată')
    await user.click(within(form).getByRole('button', { name: 'Anulează' }))
    expect(screen.queryByRole('form')).not.toBeInTheDocument()
    expect(revoked).toEqual([])

    await user.click(within(first).getByRole('button', { name: 'Revocă cheia Corporate VPN' }))
    form = screen.getByRole('form', { name: 'Revocă cheia „Corporate VPN”' })
    await user.click(within(form).getByRole('button', { name: 'Confirmă' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Cheia „Corporate VPN” a fost revocată.')
    expect(revoked).toEqual(['3'])
    expect(listed.count).toBe(2)
    // The list now shows the key as revoked, with nothing left to revoke.
    expect(await within(rows(table)[0]).findAllByText('Revocată')).not.toHaveLength(0)
    expect(within(rows(table)[0]).queryByRole('button')).not.toBeInTheDocument()
  })

  it('tells an empty list apart', async () => {
    serveKeys(() => [])
    signedInAs(makeUser('owner', { id: 1 }))
    renderApp('/org/api-keys')

    expect(await screen.findByText('Nu există încă nicio cheie.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cheie nouă' })).toBeInTheDocument()
  })
})
