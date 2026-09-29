import { useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { addDays, format, startOfWeek } from 'date-fns'
import { toZonedTime } from 'date-fns-tz'
import { toast } from 'sonner'
import { apiClient } from '@/api/client'
import { ApiError, unwrap } from '@/api/errors'
import type { components } from '@/api/schema'
import { useAuth } from '@/auth/AuthContext'
import { useBookingDetail, useBookingsList } from '@/hooks/useBookings'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/StatusBadge'
import { formatUZS } from '@/lib/format'
import { cn } from '@/lib/utils'

type Booking = components['schemas']['Booking']

function timeLabel(iso: string, timeZone: string): string {
  return toZonedTime(new Date(iso), timeZone).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function BookingChip({
  booking,
  timeZone,
  onOpen,
}: {
  booking: Booking
  timeZone: string
  onOpen: () => void
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full flex-col items-start gap-0.5 rounded-md border border-border p-2 text-left text-xs hover:border-primary"
    >
      <span className="font-medium">
        {timeLabel(booking.start, timeZone)} &middot; {booking.customer_name}
      </span>
      <div className="flex items-center gap-1">
        <StatusBadge status={booking.status} />
        {booking.has_time_off_conflict && (
          <Badge variant="outline" className="border-warning text-warning">
            Time off conflict
          </Badge>
        )}
      </div>
    </button>
  )
}

function BookingDetailSheet({
  bookingId,
  onClose,
}: {
  bookingId: number | null
  onClose: () => void
}) {
  const { data: detail, isLoading } = useBookingDetail(bookingId)
  const { user } = useAuth()
  const timeZone = user?.timezone ?? 'UTC'
  const queryClient = useQueryClient()
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleConfirm() {
    if (!detail) return
    setIsSubmitting(true)
    try {
      await unwrap(
        apiClient.POST('/api/v1/bookings/{id}/confirm/', {
          params: { path: { id: detail.id } },
        }),
      )
      toast.success('Booking confirmed.')
      void queryClient.invalidateQueries({ queryKey: ['bookings'] })
      onClose()
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Something went wrong. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleComplete() {
    if (!detail) return
    setIsSubmitting(true)
    try {
      await unwrap(
        apiClient.POST('/api/v1/bookings/{id}/complete/', {
          params: { path: { id: detail.id } },
        }),
      )
      toast.success('Booking marked as completed.')
      void queryClient.invalidateQueries({ queryKey: ['bookings'] })
      onClose()
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Something went wrong. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const canConfirm = detail?.status === 'pending' && detail.submitted_at !== null
  const canComplete = detail?.status === 'confirmed' && new Date(detail.end) <= new Date()

  return (
    <Sheet open={bookingId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Booking details</SheetTitle>
          <SheetDescription>Status history and available actions.</SheetDescription>
        </SheetHeader>
        <div className="space-y-4 px-4">
          {isLoading || !detail ? (
            <Skeleton className="h-48" />
          ) : (
            <>
              <div className="flex items-center justify-between">
                <StatusBadge status={detail.status} />
                <span className="font-medium">{formatUZS(detail.price_snapshot)}</span>
              </div>
              <p className="text-sm">{detail.customer_name}</p>
              <p className="text-sm text-muted-foreground">{detail.service_name}</p>
              <p className="text-sm text-muted-foreground">
                {timeLabel(detail.start, timeZone)} &ndash;{' '}
                {timeLabel(detail.end, timeZone)}
              </p>
              {detail.has_time_off_conflict && (
                <p className="text-sm text-warning">
                  This booking overlaps time off you&apos;ve recorded — review before
                  proceeding.
                </p>
              )}

              <div className="space-y-2">
                <span className="text-sm font-medium">Status history</span>
                <ol className="space-y-2 border-l border-border pl-4">
                  {detail.status_logs.map((log) => (
                    <li key={log.id} className="text-sm">
                      <span className="font-medium">{log.to_status}</span>{' '}
                      <span className="text-muted-foreground">
                        {timeLabel(log.created_at, timeZone)}
                      </span>
                      {log.reason && (
                        <p className="text-muted-foreground">{log.reason}</p>
                      )}
                    </li>
                  ))}
                </ol>
              </div>

              <div className="flex flex-wrap gap-2 pt-2">
                {canConfirm && (
                  <Button disabled={isSubmitting} onClick={() => void handleConfirm()}>
                    Confirm
                  </Button>
                )}
                {canComplete && (
                  <Button disabled={isSubmitting} onClick={() => void handleComplete()}>
                    Mark completed
                  </Button>
                )}
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

export function Schedule() {
  const { user } = useAuth()
  const timeZone = user?.timezone ?? 'UTC'
  const providerId = user?.provider_id ?? null
  const [view, setView] = useState<'day' | 'week'>('week')
  const [anchor, setAnchor] = useState(() => new Date())
  const [openBookingId, setOpenBookingId] = useState<number | null>(null)

  const days = useMemo(() => {
    if (view === 'day') return [anchor]
    const weekStart = startOfWeek(anchor, { weekStartsOn: 1 })
    return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))
  }, [view, anchor])

  const dateFrom = format(days[0] ?? anchor, 'yyyy-MM-dd')
  const dateTo = format(days[days.length - 1] ?? anchor, 'yyyy-MM-dd')

  const { data, isLoading, isError } = useBookingsList({
    provider: providerId ?? undefined,
    date_from: dateFrom,
    date_to: dateTo,
  })

  const bookingsByDay = useMemo(() => {
    const map = new Map<string, Booking[]>()
    for (const day of days) map.set(format(day, 'yyyy-MM-dd'), [])
    for (const booking of data?.results ?? []) {
      const dayKey = format(toZonedTime(new Date(booking.start), timeZone), 'yyyy-MM-dd')
      map.get(dayKey)?.push(booking)
    }
    for (const list of map.values()) list.sort((a, b) => a.start.localeCompare(b.start))
    return map
  }, [data, days, timeZone])

  if (providerId === null) {
    return <p className="text-sm text-muted-foreground">Loading your profile...</p>
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2">
          <Button
            variant={view === 'day' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setView('day')}
          >
            Day
          </Button>
          <Button
            variant={view === 'week' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setView('week')}
          >
            Week
          </Button>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAnchor((d) => addDays(d, view === 'day' ? -1 : -7))}
          >
            &larr; Previous
          </Button>
          <Button variant="outline" size="sm" onClick={() => setAnchor(new Date())}>
            Today
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAnchor((d) => addDays(d, view === 'day' ? 1 : 7))}
          >
            Next &rarr;
          </Button>
        </div>
      </div>

      {isLoading && <Skeleton className="h-64" />}
      {isError && (
        <p className="text-sm text-muted-foreground">Couldn&apos;t load your schedule.</p>
      )}

      {!isLoading && !isError && (
        <div
          className={cn(
            'grid gap-3',
            view === 'week' ? 'grid-cols-1 sm:grid-cols-7' : 'grid-cols-1',
          )}
        >
          {days.map((day) => {
            const key = format(day, 'yyyy-MM-dd')
            const dayBookings = bookingsByDay.get(key) ?? []
            return (
              <div key={key} className="space-y-2">
                <div className="text-sm font-medium">{format(day, 'EEE d MMM')}</div>
                <div className="space-y-2">
                  {dayBookings.length === 0 && (
                    <p className="text-xs text-muted-foreground">No bookings</p>
                  )}
                  {dayBookings.map((booking) => (
                    <BookingChip
                      key={booking.id}
                      booking={booking}
                      timeZone={timeZone}
                      onOpen={() => setOpenBookingId(booking.id)}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <BookingDetailSheet
        bookingId={openBookingId}
        onClose={() => setOpenBookingId(null)}
      />
    </div>
  )
}
