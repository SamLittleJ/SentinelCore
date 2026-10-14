/**
 * The headers the console is served with (threat model T-01, T-03).
 *
 * `vite preview` serves the production build with `productionHeaders`. Any
 * server that serves the build in production (nginx, in phase B) must send
 * the same.
 */

type Directives = Record<string, string>

const production: Directives = {
  'default-src': "'self'",
  // Only the bundle's own files: an injected <script> or onclick= never runs.
  'script-src': "'self'",
  // Radix dialogs and menus add <style> elements while they are open
  // (react-remove-scroll), so inline styles stay allowed. Styles cannot run code.
  'style-src': "'self' 'unsafe-inline'",
  'img-src': "'self' data:",
  'font-src': "'self'",
  // The API is reached through /api on the same origin.
  'connect-src': "'self'",
  'object-src': "'none'",
  'base-uri': "'none'",
  'form-action': "'self'",
  // No other site can show the console in a frame (clickjacking).
  'frame-ancestors': "'none'",
}

// Vite's dev server adds the inline React Refresh preamble to the page and
// reloads it over a websocket.
const development: Directives = {
  ...production,
  'script-src': "'self' 'unsafe-inline'",
  'connect-src': "'self' ws:",
}

function policy(directives: Directives): string {
  return Object.entries(directives)
    .map(([name, sources]) => `${name} ${sources}`)
    .join('; ')
}

const common = {
  'X-Content-Type-Options': 'nosniff',
  // frame-ancestors, for browsers that predate it.
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'no-referrer',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
  'Cross-Origin-Opener-Policy': 'same-origin',
}

export const productionHeaders: Record<string, string> = {
  'Content-Security-Policy': policy(production),
  ...common,
}

export const developmentHeaders: Record<string, string> = {
  'Content-Security-Policy': policy(development),
  ...common,
}
