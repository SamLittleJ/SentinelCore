const DEFAULT_PATH = '/me'

/**
 * Where to go after login. Only same-app paths are accepted, so a crafted
 * link like /login?next=https://evil.example cannot redirect elsewhere.
 */
export function safeNextPath(next: string | null): string {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) {
    return DEFAULT_PATH
  }
  if (next === '/login' || next.startsWith('/login?')) {
    return DEFAULT_PATH
  }
  return next
}
