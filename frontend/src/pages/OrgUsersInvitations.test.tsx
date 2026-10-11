import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { Role } from '@/features/auth/api'
import type { Invitation } from '@/features/org/api'
import { renderApp } from '@/test/render'
import { makeInvitation, makeUser, server, signedInAs } from '@/test/server'

const HOUR = 3600_000
// Not a real token: the shape the API answers with.
const TOKEN = `sci_n3w1nv1t_${'example'.repeat(6)}`

const dana = makeInvitation({ id: 14, email: 'dana.ilie@example.com', role: 'user' })
const newAdmin = makeInvitation({
  id: 13,
  email: 'victor.admin@example.com',
  role: 'admin',
  prefix: 'a0a0a0a0',
})
const joined = makeInvitation({
  id: 12,
  email: 'mara.ene@example.com',
  role: 'security_analyst',
  accepted_at: new Date(Date.now() - 2 * HOUR).toISOString(),
  accepted_user_id: 31,
})
const lapsed = makeInvitation({
  id: 11,
  email: 'old.contact@example.com',
  expires_at: new Date(Date.now() - 24 * HOUR).toISOString(),
})

/** Answers the invitation list with `invitations()` at each request. */
function serveInvitations(invitations: () => Invitation[]) {
  const requests = { count: 0 }
  server.use(
    http.get('/api/admin/invitations', () => {
      requests.count += 1
      return HttpResponse.json(invitations())
    }),
  )
  return requests
}

async function openUsers(role: Role) {
  signedInAs(makeUser(role, { id: 1 }))
  const result = renderApp('/org/users')
  const section = await screen.findByRole('region', { name: 'Invitații' })
  return { ...result, section }
}

function rows(table: HTMLElement) {
  return within(table).getAllByRole('row').slice(1)
}

describe('invitations on the users page', () => {
  it('shows an analyst the open invitations and folds the rest away, with no actions', async () => {
    serveInvitations(() => [dana, newAdmin, joined, lapsed])
    const { section } = await openUsers('security_analyst')

    const open = await within(section).findByRole('table', { name: 'Invitații deschise' })
    const [first, second] = rows(open)
    expect(rows(open)).toHaveLength(2)
    expect(first).toHaveTextContent('dana.ilie@example.com')
    expect(first).toHaveTextContent(`sci_${dana.prefix}_…`)
    expect(first).toHaveTextContent('Utilizator')
    expect(first).toHaveTextContent('Deschisă')
    expect(second).toHaveTextContent('Administrator')

    const history = within(section).getByText(
      'Istoric: 2 invitații folosite, revocate sau expirate',
    )
    const past = within(history.closest('details')!).getByRole('table', {
      name: 'Istoricul invitațiilor',
      hidden: true,
    })
    expect(rows(past)[0]).toHaveTextContent('Acceptată')
    expect(rows(past)[1]).toHaveTextContent('Expirată')
    // Whoever joined is one click from their account.
    expect(within(past).getByRole('link', { name: 'mara.ene@example.com', hidden: true })).toHaveAttribute(
      'href',
      '/org/users/31',
    )

    expect(within(section).queryByRole('button', { name: 'Invită o persoană' })).not.toBeInTheDocument()
    expect(within(section).queryByRole('button', { name: /Revocă/ })).not.toBeInTheDocument()
  })

  it('lets an admin invite with an everyday role and shows the link once', async () => {
    const user = userEvent.setup()
    const created = makeInvitation({ id: 15, email: 'nou.coleg@example.com', prefix: 'n3w1nv1t' })
    let invitations = [dana]
    const listed = serveInvitations(() => invitations)
    const bodies: unknown[] = []
    server.use(
      http.post('/api/admin/invitations', async ({ request }) => {
        bodies.push(await request.json())
        invitations = [created, dana]
        return HttpResponse.json(
          { invitation: { ...created, role: 'security_analyst' }, token: TOKEN },
          { status: 201 },
        )
      }),
    )
    const { router, queryClient, section } = await openUsers('admin')

    await user.click(within(section).getByRole('button', { name: 'Invită o persoană' }))
    const form = within(section).getByRole('form', { name: 'Invită o persoană' })
    const roles = within(form).getByRole('group', { name: 'Rol' })
    // An admin cannot add another admin.
    expect(within(roles).getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Utilizator',
      'Analist de securitate',
    ])
    const confirm = within(form).getByRole('button', { name: 'Confirmă' })
    await user.type(within(form).getByLabelText('Email'), 'nu-e-email')
    expect(confirm).toBeDisabled()
    await user.clear(within(form).getByLabelText('Email'))
    await user.type(within(form).getByLabelText('Email'), '  Nou.Coleg@Example.com ')
    await user.click(within(roles).getByRole('button', { name: 'Analist de securitate' }))
    await user.click(confirm)

    const panel = await screen.findByRole('region', {
      name: 'Invitația pentru nou.coleg@example.com a fost creată',
    })
    expect(bodies).toEqual([{ email: 'nou.coleg@example.com', role: 'security_analyst' }])
    const link = `${window.location.origin}/invite#${TOKEN}`
    expect(panel).toHaveTextContent(link)
    expect(panel).toHaveTextContent('Nu va mai fi afișat')

    await user.click(within(panel).getByRole('button', { name: 'Copiază link-ul' }))
    expect(await navigator.clipboard.readText()).toBe(link)
    expect(within(panel).getByRole('status')).toHaveTextContent('Link-ul a fost copiat.')

    // The list shows the new invitation by its prefix only.
    expect(listed.count).toBe(2)
    const open = within(section).getByRole('table', { name: 'Invitații deschise' })
    expect(rows(open)[0]).toHaveTextContent('sci_n3w1nv1t_…')

    // The token lives in the page's state, and nowhere that outlasts it.
    expect(router.state.location.pathname + router.state.location.search).not.toContain(TOKEN)
    expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain(TOKEN)
    expect(JSON.stringify(queryClient.getQueryCache().getAll().map((q) => q.state.data))).not.toContain(
      TOKEN,
    )
    expect(
      JSON.stringify(queryClient.getMutationCache().getAll().map((m) => m.state.data)),
    ).not.toContain(TOKEN)

    await user.click(within(panel).getByRole('button', { name: 'Am trimis link-ul' }))
    expect(document.body).not.toHaveTextContent(TOKEN)
  })

  it('offers the owner the admin role too', async () => {
    const user = userEvent.setup()
    const { section } = await openUsers('owner')

    await user.click(within(section).getByRole('button', { name: 'Invită o persoană' }))
    const roles = within(section).getByRole('group', { name: 'Rol' })
    expect(within(roles).getByRole('button', { name: 'Administrator' })).toBeInTheDocument()
  })

  it('says when the email already has an account', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('/api/admin/invitations', () =>
        HttpResponse.json({ detail: 'An account with this email already exists' }, { status: 409 }),
      ),
    )
    const { section } = await openUsers('admin')

    await user.click(within(section).getByRole('button', { name: 'Invită o persoană' }))
    await user.type(within(section).getByLabelText('Email'), 'mihai.pop@example.com')
    await user.click(within(section).getByRole('button', { name: 'Confirmă' }))

    expect(await within(section).findByRole('alert')).toHaveTextContent(
      'Există deja un cont cu acest email.',
    )
  })

  it('lets an admin revoke only the invitations whose role they may offer', async () => {
    const user = userEvent.setup()
    let invitations = [dana, newAdmin]
    serveInvitations(() => invitations)
    const revoked: string[] = []
    server.use(
      http.post('/api/admin/invitations/:id/revoke', ({ params }) => {
        revoked.push(String(params.id))
        const done = { ...dana, revoked_at: new Date().toISOString() }
        invitations = [done, newAdmin]
        return HttpResponse.json(done)
      }),
    )
    const { section } = await openUsers('admin')

    const open = await within(section).findByRole('table', { name: 'Invitații deschise' })
    expect(
      within(open).queryByRole('button', { name: 'Revocă invitația pentru victor.admin@example.com' }),
    ).not.toBeInTheDocument()
    await user.click(
      within(open).getByRole('button', { name: 'Revocă invitația pentru dana.ilie@example.com' }),
    )
    const confirm = within(section).getByRole('form', {
      name: 'Revocă invitația pentru dana.ilie@example.com',
    })
    await user.click(within(confirm).getByRole('button', { name: 'Confirmă' }))

    expect(await within(section).findByRole('status')).toHaveTextContent(
      'Invitația pentru dana.ilie@example.com a fost revocată.',
    )
    expect(revoked).toEqual([String(dana.id)])
    expect(
      await within(section).findByText('Istoric: 1 invitație folosită, revocată sau expirată'),
    ).toBeInTheDocument()
  })
})
