/**
 * Writes the console's security headers (security-headers.ts) as nginx
 * directives, so the image's server sends exactly what `vite preview` sends.
 *
 * Run by the image build: `node scripts/nginx-headers.ts > console-headers.conf`.
 * nginx drops a server's add_header lines in any location that has its own,
 * so the file is included in every location that serves the console.
 */

import { fileURLToPath } from 'node:url'

import { productionHeaders } from '../security-headers.ts'

export function nginxHeaders(headers: Record<string, string>): string {
  return Object.entries(headers)
    .map(([name, value]) => {
      // Values are written between double quotes, where `$` starts a
      // variable: anything nginx would read differently is refused.
      if (!/^[\w-]+$/.test(name) || /["\\$\n]/.test(value)) {
        throw new Error(`Cannot write the ${name} header for nginx`)
      }
      return `add_header ${name} "${value}" always;`
    })
    .join('\n')
    .concat('\n')
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  process.stdout.write(nginxHeaders(productionHeaders))
}
