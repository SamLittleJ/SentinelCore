import { Crosshair, ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { techniqueName, techniqueUrl } from './mitre'

/** The MITRE ATT&CK technique a detection stands for, as its id. The name is
 * in the tooltip; screen readers hear what the code is. */
export function MitreBadge({ technique }: { technique: string }) {
  const { t } = useTranslation()
  return (
    <span
      title={techniqueName(technique)}
      className="inline-flex items-center gap-1 rounded border border-primary/30 bg-primary/10 px-1.5 py-0.5 font-mono text-[11px] font-medium whitespace-nowrap text-primary"
    >
      <Crosshair aria-hidden className="size-3" />
      <span className="sr-only">{t('mitre.label')} </span>
      {technique}
    </span>
  )
}

/** The technique in a record's details: its id, its name and its page on
 * attack.mitre.org, opened in a new tab without telling MITRE where from. */
export function TechniqueDetail({ technique }: { technique: string }) {
  const { t } = useTranslation()
  const name = techniqueName(technique)
  const url = techniqueUrl(technique)
  return (
    <span className="flex flex-col items-start gap-1">
      <span>
        <span className="font-mono text-xs">{technique}</span>
        {name && <span> · {name}</span>}
      </span>
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded-sm text-sm text-primary hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {t('mitre.open')}
          <ExternalLink aria-hidden className="size-3.5" />
          <span className="sr-only">{t('mitre.newTab')}</span>
        </a>
      )}
    </span>
  )
}
