// The API's rules for an organization's name and slug, mirrored so the form
// can say what is wrong before sending. The API still decides.

export const ORGANIZATION_NAME_MIN = 2
export const ORGANIZATION_NAME_MAX = 100
export const SLUG_MIN = 2
export const SLUG_MAX = 40

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

export function validOrganizationName(name: string): boolean {
  const trimmed = name.trim()
  return trimmed.length >= ORGANIZATION_NAME_MIN && trimmed.length <= ORGANIZATION_NAME_MAX
}

export function validSlug(slug: string): boolean {
  return slug.length >= SLUG_MIN && slug.length <= SLUG_MAX && SLUG.test(slug)
}

/** A slug suggested from `name`: "Globex Europa" becomes "globex-europa",
 * "Ștefan & Fiii" becomes "stefan-fiii". */
export function slugFrom(name: string): string {
  return name
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .slice(0, SLUG_MAX)
    .replace(/^-+|-+$/g, '')
}
