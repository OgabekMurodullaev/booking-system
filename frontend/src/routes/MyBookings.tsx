import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toZonedTime } from 'date-fns-tz'
import { toast } from 'sonner'
import { apiClient } from '@/api/client'
import { ApiError, unwrap } from '@/api/errors'
import type { components } from '@/api/schema'
import { useAuth } from '@/auth/AuthContext'
import { useBookingDetail, useMyBookings } from '@/hooks/useBookings'
import { useProviders } from '@/hooks/useServices'
import { downloadBookingIcs } from '@/lib/ics'
import { formatUZS } from '@/lib/format'
import { cn } from '@/lib/utils'
import { StatusBadge } from '@/components/StatusBadge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

type Booking = components['schemas']['Booking']

function timeLabel(iso: string, timeZone: string): string {
  return toZonedTime(new Date(iso), timeZone).toLocaleString([], {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function CancelDialog({
  booking,
  onCancelled,
}: {
  booking: Booking
  onCancelled: () => void
}) {
  const [reason, setReason] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleConfirm() {
    setIsSubmitting(true)
    try {
      await unwrap(
        apiClient.POST('/api/v1/bookings/{id}/cancel/', {
          params: { path: { id: booking.id } },
          body: { reason },
        }),
      )
      toast.success('Booking cancelled.')
      onCancelled()
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

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline">Cancel booking</Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Cancel this booking?</AlertDialogTitle>
          <AlertDialogDescription>
            {booking.would_be_late_cancellation
              ? "This is within the business's cancellation window, so it will be flagged as a late cancellation."
              : 'Let the business know why, if you like.'}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason (optional)"
          rows={3}
          className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        />
        <AlertDialogFooter>
          <AlertDialogCancel>Keep booking</AlertDialogCancel>
          <AlertDialogAction disabled={isSubmitting} onClick={() => void handleConfirm()}>
            {isSubmitting ? 'Cancelling...' : 'Confirm cancellation'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function BookingDetailSheet({
  bookingId,
  onClose,
  onCancelled,
}: {
  bookingId: number | null
  onClose: () => void
  onCancelled: () => void
}) {
  const { data: detail, isLoading } = useBookingDetail(bookingId)
  const { user } = useAuth()
  const timeZone = user?.timezone ?? 'UTC'

  return (
    <Sheet open={bookingId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Booking details</SheetTitle>
          <SheetDescription>
            Status history and actions for this booking.
          </SheetDescription>
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
              <p className="text-sm text-muted-foreground">
                {timeLabel(detail.start, timeZone)}
              </p>

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
                <Button
                  variant="outline"
                  onClick={() => void downloadBookingIcs(detail.id)}
                >
                  Add to calendar
                </Button>
                {(detail.status === 'pending' || detail.status === 'confirmed') && (
                  <CancelDialog booking={detail} onCancelled={onCancelled} />
                )}
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function BookingCard({ booking, onOpen }: { booking: Booking; onOpen: () => void }) {
  const { data: providersPage } = useProviders()
  const { user } = useAuth()
  const providerName = providersPage?.results.find((p) => p.id === booking.provider)?.user
    .full_name

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => e.key === 'Enter' && onOpen()}
      className={cn('cursor-pointer transition-colors hover:border-primary')}
    >
      <CardContent className="flex items-center justify-between gap-4 py-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <StatusBadge status={booking.status} />
          </div>
          <p className="text-sm">{timeLabel(booking.start, user?.timezone ?? 'UTC')}</p>
          {providerName && (
            <p className="text-sm text-muted-foreground">{providerName}</p>
          )}
        </div>
        <span className="font-medium">{formatUZS(booking.price_snapshot)}</span>
      </CardContent>
    </Card>
  )
}

function BookingList({
  bookings,
  emptyLabel,
  onOpen,
}: {
  bookings: Booking[]
  emptyLabel: string
  onOpen: (id: number) => void
}) {
  if (bookings.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>
  }
  return (
    <div className="space-y-3">
      {bookings.map((booking) => (
        <BookingCard
          key={booking.id}
          booking={booking}
          onOpen={() => onOpen(booking.id)}
        />
      ))}
    </div>
  )
}

export function MyBookings() {
  const { data, isLoading, isError } = useMyBookings()
  const queryClient = useQueryClient()
  const [openBookingId, setOpenBookingId] = useState<number | null>(null)

  function handleCancelled() {
    setOpenBookingId(null)
    void queryClient.invalidateQueries({ queryKey: ['bookings'] })
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
      </div>
    )
  }

  if (isError) {
    return (
      <p className="text-sm text-muted-foreground">
        Couldn&apos;t load your bookings. Please try again.
      </p>
    )
  }

  const bookings = data?.results ?? []
  const upcoming = bookings.filter(
    (b) => b.status === 'pending' || b.status === 'confirmed',
  )
  const past = bookings.filter((b) => b.status === 'completed')
  const cancelled = bookings.filter((b) => b.status === 'cancelled')

  return (
    <>
      <Tabs defaultValue="upcoming">
        <TabsList>
          <TabsTrigger value="upcoming">Upcoming</TabsTrigger>
          <TabsTrigger value="past">Past</TabsTrigger>
          <TabsTrigger value="cancelled">Cancelled</TabsTrigger>
        </TabsList>
        <TabsContent value="upcoming" className="pt-4">
          <BookingList
            bookings={upcoming}
            emptyLabel="No upcoming bookings."
            onOpen={setOpenBookingId}
          />
        </TabsContent>
        <TabsContent value="past" className="pt-4">
          <BookingList
            bookings={past}
            emptyLabel="No past bookings yet."
            onOpen={setOpenBookingId}
          />
        </TabsContent>
        <TabsContent value="cancelled" className="pt-4">
          <BookingList
            bookings={cancelled}
            emptyLabel="No cancelled bookings."
            onOpen={setOpenBookingId}
          />
        </TabsContent>
      </Tabs>

      <BookingDetailSheet
        bookingId={openBookingId}
        onClose={() => setOpenBookingId(null)}
        onCancelled={handleCancelled}
      />
    </>
  )
}
