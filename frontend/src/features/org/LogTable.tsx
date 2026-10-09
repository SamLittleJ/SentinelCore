import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

export interface LogColumn<Item> {
  header: string
  cell: (item: Item) => ReactNode
  // Applies to the cells, not the header.
  className?: string
}

interface LogTableProps<Item extends { id: number; created_at: string }> {
  label: string
  items: Item[]
  // What the record is, shown as the button that opens its details.
  describe: (item: Item) => string
  // Shown beside the description, such as a detection's technique.
  annotate?: (item: Item) => ReactNode
  // Columns after the time and the description.
  columns: LogColumn<Item>[]
  onSelect: (item: Item) => void
}

/** A newest-first log. Each row opens the record's details: by keyboard
 * through its description button, by mouse anywhere on the row. */
export function LogTable<Item extends { id: number; created_at: string }>({
  label,
  items,
  describe,
  annotate,
  columns,
  onSelect,
}: LogTableProps<Item>) {
  const { t } = useTranslation()
  const format = useFormatters()

  return (
    <div className="w-full overflow-x-auto rounded-lg border bg-card">
      <table aria-label={label} className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('orgLog.time')}
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('orgLog.event')}
            </th>
            {columns.map((column) => (
              <th key={column.header} scope="col" className="px-4 py-2.5 font-medium">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              onClick={() => onSelect(item)}
              className="cursor-pointer border-b transition-colors last:border-b-0 hover:bg-accent/40"
            >
              <td className="px-4 py-2.5 font-mono text-xs whitespace-nowrap text-muted-foreground">
                <time dateTime={item.created_at} title={format.relative(item.created_at)}>
                  {format.dateTime(item.created_at)}
                </time>
              </td>
              <td className="min-w-56 px-4 py-2.5">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  {/* Its click, also from Enter or Space, bubbles to the row. */}
                  <button
                    type="button"
                    className="rounded-sm text-left hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                  >
                    {describe(item)}
                  </button>
                  {annotate?.(item)}
                </div>
              </td>
              {columns.map((column) => (
                <td key={column.header} className={cn('px-4 py-2.5', column.className)}>
                  {column.cell(item)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
