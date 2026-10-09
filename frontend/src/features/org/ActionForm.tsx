import { useId, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type Notice = { tone: 'ok' | 'error'; text: string }

/** The outcome of an action: a status when it worked, an alert when not. */
export function ActionNotice({ notice }: { notice: Notice }) {
  return (
    <p
      role={notice.tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'rounded-lg px-4 py-3',
        notice.tone === 'error' ? 'bg-sev-incident-bg text-sev-incident' : 'bg-sev-ok-bg text-sev-ok',
      )}
    >
      {notice.text}
    </p>
  )
}

interface ActionFormProps {
  title: string
  help: string
  children?: ReactNode
  confirmDisabled?: boolean
  destructive?: boolean
  pending: boolean
  onCancel: () => void
  onSubmit: () => void
}

/** A confirmation step in the page, not a dialog: the action's name, what it
 * does, its fields if any, and confirm or cancel. */
export function ActionForm({
  title,
  help,
  children,
  confirmDisabled = false,
  destructive = false,
  pending,
  onCancel,
  onSubmit,
}: ActionFormProps) {
  const { t } = useTranslation()
  const titleId = useId()
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmit()
  }

  return (
    <form
      aria-labelledby={titleId}
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-lg border border-sev-warn/40 bg-sev-warn-bg/40 px-4 py-4"
    >
      <div className="flex flex-col gap-1">
        <h3 id={titleId} className="font-medium">
          {title}
        </h3>
        <p className="text-sm text-muted-foreground">{help}</p>
      </div>
      {children}
      <div className="flex gap-2">
        <Button
          type="submit"
          variant={destructive ? 'destructive' : 'default'}
          disabled={confirmDisabled || pending}
          // A form without fields starts on its confirmation.
          autoFocus={children === undefined}
        >
          {t('userDetail.confirm')}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t('userDetail.cancel')}
        </Button>
      </div>
    </form>
  )
}

export function ConfirmForm(
  props: Omit<ActionFormProps, 'onSubmit' | 'children'> & { onConfirm: () => void },
) {
  const { onConfirm, ...frame } = props
  return <ActionForm {...frame} onSubmit={onConfirm} />
}
