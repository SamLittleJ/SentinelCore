import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { Organization } from '@/features/org/api'
import { renderApp } from '@/test/render'
import { makeOrganization, makeUser, server, signedInAs } from '@/test/server'

const acme = makeOrganization({ id: 1, name: 'Acme', slug: 'acme', members: 36 })
const initech = makeOrganization({
  id: 3,
  name: 'Initech',
  slug: 'initech',
  members: 4,
  suspended_at: '2026-10-10T08:00:00Z',
})

/** Answers the list with `organizations()` at each request, and counts them. */
function serveOrganizations(organizations: () => Organization[]) {
  const requests = { count: 0 }
  server.use(
    http.get('/api/admin/organizations', () => {
      requests.count += 1
      return HttpResponse.json(organizations())
    }),
  )
  return requests
}

async function openAsOwner() {
  signedInAs(makeUser('owner', { id: 1 }))
  const result = renderApp('/org/organizations')
  const table = await screen.findByRole('table', { name: 'Organizații' })
  return { ...result, table, user: userEvent.setup() }
}

function rows(table: HTMLElement) {
  return within(table).getAllByRole('row').slice(1)
}

describe('organizations page', () => {
  it('lists every organization with its state and members', async () => {
    serveOrganizations(() => [acme, initech])
    const { table } = await openAsOwner()

    const [first, second] = rows(table)
    expect(first).toHaveTextContent('Acme')
    expect(first).toHaveTextContent('acme')
    expect(first).toHaveTextContent('Activă')
    expect(first).toHaveTextContent('36')
    expect(within(first).getByRole('button', { name: 'Suspendă Acme' })).toBeInTheDocument()
    expect(second).toHaveTextContent('Suspendată')
    expect(within(second).getByRole('button', { name: 'Reactivează Initech' })).toBeInTheDocument()
    expect(within(second).queryByRole('button', { name: /Suspendă/ })).not.toBeInTheDocument()
  })

  it('suggests a slug from the name and creates the organization', async () => {
    let organizations = [acme]
    serveOrganizations(() => organizations)
    let sent: unknown
    server.use(
      http.post('/api/admin/organizations', async ({ request }) => {
        sent = await request.json()
        const created = makeOrganization({ id: 4, name: 'Globex Europa', slug: 'globex-eu', members: 0 })
        organizations = [created, acme]
        return HttpResponse.json(created, { status: 201 })
      }),
    )
    const { user } = await openAsOwner()

    await user.click(screen.getByRole('button', { name: 'Organizație nouă' }))
    const confirm = screen.getByRole('button', { name: 'Confirmă' })
    expect(confirm).toBeDisabled()
    await user.type(screen.getByLabelText('Nume'), 'Globex Europa')
    const slug = screen.getByLabelText('Slug')
    expect(slug).toHaveValue('globex-europa')
    // Edited by hand, it stops following the name.
    await user.clear(slug)
    await user.type(slug, 'globex-eu')
    await user.type(screen.getByLabelText('Nume'), ' ')
    expect(slug).toHaveValue('globex-eu')
    await user.click(confirm)

    expect(await screen.findByRole('status')).toHaveTextContent('Organizația „Globex Europa” a fost creată.')
    expect(sent).toEqual({ name: 'Globex Europa', slug: 'globex-eu' })
    expect(await screen.findByRole('cell', { name: /Globex Europa/ })).toBeInTheDocument()
  })

  it('refuses a slug the API would refuse, before sending it', async () => {
    serveOrganizations(() => [acme])
    const { user } = await openAsOwner()

    await user.click(screen.getByRole('button', { name: 'Organizație nouă' }))
    await user.type(screen.getByLabelText('Nume'), 'Acme 2')
    const slug = screen.getByLabelText('Slug')
    await user.clear(slug)
    await user.type(slug, 'Acme_2')

    expect(slug).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('button', { name: 'Confirmă' })).toBeDisabled()
  })

  it('says when the name or slug is taken', async () => {
    serveOrganizations(() => [acme])
    server.use(
      http.post('/api/admin/organizations', () =>
        HttpResponse.json(
          { detail: 'An organization with this name or slug already exists' },
          { status: 409 },
        ),
      ),
    )
    const { user } = await openAsOwner()

    await user.click(screen.getByRole('button', { name: 'Organizație nouă' }))
    await user.type(screen.getByLabelText('Nume'), 'Acme')
    await user.click(screen.getByRole('button', { name: 'Confirmă' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Există deja o organizație cu acest nume sau slug.',
    )
  })

  it('renames an organization, keeping its slug', async () => {
    serveOrganizations(() => [acme])
    let sent: unknown
    server.use(
      http.patch('/api/admin/organizations/1', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({ ...acme, name: 'Acme Corp' })
      }),
    )
    const { user } = await openAsOwner()

    await user.click(screen.getByRole('button', { name: 'Redenumește Acme' }))
    expect(screen.getByText(/Slug-ul rămâne „acme”/)).toBeInTheDocument()
    const name = screen.getByLabelText('Nume')
    expect(screen.getByRole('button', { name: 'Confirmă' })).toBeDisabled()
    await user.clear(name)
    await user.type(name, 'Acme Corp')
    await user.click(screen.getByRole('button', { name: 'Confirmă' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Organizația se numește acum „Acme Corp”.')
    expect(sent).toEqual({ name: 'Acme Corp' })
  })

  it('starts each form afresh when another organization is picked', async () => {
    const globex = makeOrganization({ id: 2, name: 'Globex', slug: 'globex', members: 3 })
    serveOrganizations(() => [acme, globex])
    const { user } = await openAsOwner()

    await user.click(screen.getByRole('button', { name: 'Redenumește Acme' }))
    await user.type(screen.getByLabelText('Nume'), ' Corp')
    await user.click(screen.getByRole('button', { name: 'Redenumește Globex' }))
    expect(screen.getByLabelText('Nume')).toHaveValue('Globex')

    await user.click(screen.getByRole('button', { name: 'Suspendă Acme' }))
    await user.type(screen.getByLabelText('Scrie acme ca să confirmi'), 'acme')
    await user.click(screen.getByRole('button', { name: 'Suspendă Globex' }))
    expect(screen.getByLabelText('Scrie globex ca să confirmi')).toHaveValue('')
  })

  it('suspends an organization only once its slug is typed', async () => {
    let organizations = [acme]
    serveOrganizations(() => organizations)
    let suspended = 0
    server.use(
      http.post('/api/admin/organizations/1/suspend', () => {
        suspended += 1
        organizations = [{ ...acme, suspended_at: new Date().toISOString() }]
        return HttpResponse.json(organizations[0])
      }),
    )
    const { user, table } = await openAsOwner()

    await user.click(screen.getByRole('button', { name: 'Suspendă Acme' }))
    const confirm = screen.getByRole('button', { name: 'Confirmă' })
    const typed = screen.getByLabelText('Scrie acme ca să confirmi')
    await user.type(typed, 'Acme')
    expect(confirm).toBeDisabled()
    await user.clear(typed)
    await user.type(typed, 'acme')
    expect(confirm).toBeEnabled()
    await user.click(confirm)

    expect(await screen.findByRole('status')).toHaveTextContent('Organizația „Acme” a fost suspendată.')
    expect(suspended).toBe(1)
    expect(await within(table).findAllByText('Suspendată')).not.toHaveLength(0)
  })

  it('reactivates a suspended organization', async () => {
    serveOrganizations(() => [initech])
    let reactivated = 0
    server.use(
      http.post('/api/admin/organizations/3/reactivate', () => {
        reactivated += 1
        return HttpResponse.json({ ...initech, suspended_at: null })
      }),
    )
    const { user } = await openAsOwner()

    await user.click(screen.getByRole('button', { name: 'Reactivează Initech' }))
    await user.click(screen.getByRole('button', { name: 'Confirmă' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Organizația „Initech” a fost reactivată.')
    expect(reactivated).toBe(1)
  })

  it('is the owner’s alone: an admin gets a refusal and no list is loaded', async () => {
    const requests = serveOrganizations(() => [acme])
    signedInAs(makeUser('admin'))
    renderApp('/org/organizations')

    expect(await screen.findByRole('heading', { name: 'Acces restricționat' })).toBeInTheDocument()
    expect(screen.getByText('Doar proprietarul platformei administrează organizațiile.')).toBeInTheDocument()
    expect(requests.count).toBe(0)
  })
})
