import { cn } from '@/lib/utils'
import type { components } from '@/api/schema'

type Status = components['schemas']['StatusEnum']

const STATUS_LABEL: Record<Status, string> = {
  pending: 'Pending approval',
  confirmed: 'Confirmed',
  cancelled: 'Cancelled',
  completed: 'Completed',
}

// Status colors stay in their own hue family, never the brand accent (DESIGN.md's
// "One Accent Rule") — soft tinted badges, never solid saturated fills.
const STATUS_CLASSES: Record<Status, string> = {
  pending: 'bg-warning-bg text-warning',
  confirmed: 'bg-success-bg text-success',
  completed: 'bg-success-bg text-success',
  cancelled: 'bg-destructive-bg text-destructive',
}

export function StatusBadge({
  status,
  className,
}: {
  status: Status
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        STATUS_CLASSES[status],
        className,
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  )
}
