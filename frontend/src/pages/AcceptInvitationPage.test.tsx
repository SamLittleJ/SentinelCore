import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import { server, signedInAs } from '@/test/server'

// Not a real token: the shape the API hands out.
const TOKEN = `sci_f0e1d2c3_${'example'.repeat(6)}`
const PASSWORD = 'o fraza lunga si buna'

const preview = {
  email: 'dana.ilie@example.com',
  role: 'security_analyst',
  expires_at: new Date(Date.now() + 48 * 3600_000).toISOString(),
}

/** Answers the preview, recording each request's address and body. */
function servePreview(answer: () => Response) {
  const requests: { url: string; body: unknown }[] = []
  server.use(
    http.post('/api/auth/invitations/preview', async ({ request }) => {
      requests.push({ url: request.url, body: await request.json() })
      return answer()
    }),
  )
  return requests
}

const NOT_VALID = () =>
  HttpResponse.json({ detail: 'This invitation is not valid. Ask for a new one.' }, { status: 404 })

function openInvite(hash = `#${TOKEN}`) {
  signedInAs(null)
  return renderApp(`/invite${hash}`)
}

describe('accept invitation page', () => {
  it('says a link without a token is not valid, without asking the API', async () => {
    const requests = servePreview(() => HttpResponse.json(preview))
    openInvite('')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Această invitație nu este validă. Cere una nouă.',
    )
    expect(requests).toHaveLength(0)
  })

  it('gives every invalid token the same answer', async () => {
    servePreview(NOT_VALID)
    openInvite()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Această invitație nu este validă. Cere una nouă.',
    )
  })

  it('sends the token in the body and clears it from the address', async () => {
    const requests = servePreview(() => HttpResponse.json(preview))
    const { router } = openInvite()

    expect(await screen.findByText('dana.ilie@example.com')).toBeInTheDocument()
    expect(screen.getByText('Analist de securitate')).toBeInTheDocument()
    expect(requests).toEqual([
      { url: `${window.location.origin}/api/auth/invitations/preview`, body: { token: TOKEN } },
    ])
    await waitFor(() => expect(router.state.location.hash).toBe(''))
    expect(router.state.location.pathname).toBe('/invite')
  })

  it('creates the account and opens sign-in with the email filled in', async () => {
    const user = userEvent.setup()
    servePreview(() => HttpResponse.json(preview))
    const accepted: unknown[] = []
    server.use(
      http.post('/api/auth/invitations/accept', async ({ request }) => {
        accepted.push(await request.json())
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    const { router } = openInvite()

    const submit = await screen.findByRole('button', { name: 'Creează contul' })
    await user.type(screen.getByLabelText('Nume de utilizator'), 'dana.ilie')
    // Repeated correctly, a short password is still refused.
    await user.type(screen.getByLabelText('Parolă'), 'scurta')
    await user.type(screen.getByLabelText('Repetă parola'), 'scurta')
    expect(screen.getByLabelText('Parolă')).toHaveAttribute('aria-invalid', 'true')
    expect(submit).toBeDisabled()
    await user.clear(screen.getByLabelText('Parolă'))
    await user.clear(screen.getByLabelText('Repetă parola'))
    await user.type(screen.getByLabelText('Parolă'), PASSWORD)
    await user.type(screen.getByLabelText('Repetă parola'), `${PASSWORD}!`)
    expect(screen.getByText('Parolele nu coincid.')).toBeInTheDocument()
    expect(submit).toBeDisabled()
    await user.clear(screen.getByLabelText('Repetă parola'))
    await user.type(screen.getByLabelText('Repetă parola'), PASSWORD)
    await user.click(submit)

    expect(await screen.findByRole('heading', { name: 'Autentificare' })).toBeInTheDocument()
    expect(accepted).toEqual([{ token: TOKEN, username: 'dana.ilie', password: PASSWORD }])
    expect(screen.getByRole('status')).toHaveTextContent('Contul a fost creat.')
    expect(screen.getByLabelText('Email')).toHaveValue('dana.ilie@example.com')
    expect(screen.getByLabelText('Parolă')).toHaveFocus()
    // The email travels in the router's state, not in the address.
    expect(router.state.location.pathname + router.state.location.search).toBe('/login')
  })

  it('asks for another username when the chosen one is taken', async () => {
    const user = userEvent.setup()
    servePreview(() => HttpResponse.json(preview))
    server.use(
      http.post('/api/auth/invitations/accept', () =>
        HttpResponse.json({ detail: 'Username already taken' }, { status: 400 }),
      ),
    )
    openInvite()

    await user.type(await screen.findByLabelText('Nume de utilizator'), 'mihai.pop')
    await user.type(screen.getByLabelText('Parolă'), PASSWORD)
    await user.type(screen.getByLabelText('Repetă parola'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Creează contul' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Numele de utilizator este deja folosit. Alege altul.',
    )
  })

  it('says the invitation is not valid when it stopped working meanwhile', async () => {
    const user = userEvent.setup()
    servePreview(() => HttpResponse.json(preview))
    server.use(http.post('/api/auth/invitations/accept', NOT_VALID))
    openInvite()

    await user.type(await screen.findByLabelText('Nume de utilizator'), 'dana.ilie')
    await user.type(screen.getByLabelText('Parolă'), PASSWORD)
    await user.type(screen.getByLabelText('Repetă parola'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Creează contul' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Această invitație nu este validă. Cere una nouă.',
    )
    expect(screen.queryByRole('button', { name: 'Creează contul' })).not.toBeInTheDocument()
  })
})
