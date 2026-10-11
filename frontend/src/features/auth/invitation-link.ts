export const INVITE_PATH = '/invite'

/** The link the person invited opens. The token sits in the fragment, which
 * browsers never send to a server, so it stays out of every access log. */
export function invitationLink(token: string, origin = window.location.origin): string {
  return `${origin}${INVITE_PATH}#${token}`
}

/** The token from a link's fragment, or null when there is none. */
export function tokenFromHash(hash: string): string | null {
  const token = hash.replace(/^#/, '').trim()
  return token === '' ? null : token
}
