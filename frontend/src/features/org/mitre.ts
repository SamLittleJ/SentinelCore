// The MITRE ATT&CK techniques SentinelCore detects. Their names are proper
// names, kept in English in every language, as MITRE publishes them.
const TECHNIQUE_NAMES: Record<string, string> = {
  'T1078': 'Valid Accounts',
  'T1098': 'Account Manipulation',
  'T1110.001': 'Brute Force: Password Guessing',
  'T1110.003': 'Brute Force: Password Spraying',
}

// "T1110" or "T1110.003": anything else is not used to build a link.
const TECHNIQUE_ID = /^T\d{4}(?:\.\d{3})?$/

export function techniqueName(technique: string): string | undefined {
  return TECHNIQUE_NAMES[technique]
}

/** The technique's page on attack.mitre.org, where a sub-technique's number
 * is a path segment: T1110.003 is /techniques/T1110/003/. */
export function techniqueUrl(technique: string): string | undefined {
  if (!TECHNIQUE_ID.test(technique)) return undefined
  return `https://attack.mitre.org/techniques/${technique.replace('.', '/')}/`
}
