import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toZonedTime } from 'date-fns-tz'
import { toast } from 'sonner'
import { apiClient } from '@/api/client'
import { ApiError, unwrap } from '@/api/errors'
import type { components } from '@/api/schema'
import { useAuth } from '@/auth/AuthContext'
import { useBookingsList } from '@/hooks/useBookings'
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
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { formatUZS } from '@/lib/format'

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

function RejectDialog({ booking, onDone }: { booking: Booking; onDone: () => void }) {
  const [reason, setReason] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleReject() {
    setIsSubmitting(true)
    try {
      await unwrap(
        apiClient.POST('/api/v1/bookings/{id}/cancel/', {
          params: { path: { id: booking.id } },
          body: { reason },
        }),
      )
      toast.success('Booking rejected.')
      onDone()
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
        <Button variant="outline">Reject</Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Reject this booking?</AlertDialogTitle>
          <AlertDialogDescription>Let the customer know why.</AlertDialogDescription>
        </AlertDialogHeader>
        <Textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason"
          rows={3}
        />
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction disabled={isSubmitting} onClick={() => void handleReject()}>
            {isSubmitting ? 'Rejecting...' : 'Confirm rejection'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function Approvals() {
  const { user } = useAuth()
  const timeZone = user?.timezone ?? 'UTC'
  const providerId = user?.provider_id ?? null
  const queryClient = useQueryClient()
  const [confirmingId, setConfirmingId] = useState<number | null>(null)

  const { data, isLoading, isError } = useBookingsList({
    provider: providerId ?? undefined,
    status: 'pending',
  })

  const pendingApprovals = (data?.results ?? []).filter((b) => b.submitted_at !== null)

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['bookings'] })
  }

  async function handleConfirm(booking: Booking) {
    setConfirmingId(booking.id)
    try {
      await unwrap(
        apiClient.POST('/api/v1/bookings/{id}/confirm/', {
          params: { path: { id: booking.id } },
        }),
      )
      toast.success('Booking confirmed.')
      refresh()
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Something went wrong. Please try again.',
      )
    } finally {
      setConfirmingId(null)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
    )
  }

  if (isError) {
    return (
      <p className="text-sm text-muted-foreground">
        Couldn&apos;t load pending approvals.
      </p>
    )
  }

  if (pendingApprovals.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No bookings waiting for your approval.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {pendingApprovals.map((booking) => (
        <Card key={booking.id}>
          <CardContent className="flex flex-wrap items-center justify-between gap-4 py-4">
            <div className="space-y-1">
              <p className="font-medium">{booking.customer_name}</p>
              <p className="text-sm text-muted-foreground">{booking.service_name}</p>
              <p className="text-sm text-muted-foreground">
                {timeLabel(booking.start, timeZone)}
              </p>
              <p className="text-sm font-medium">{formatUZS(booking.price_snapshot)}</p>
            </div>
            <div className="flex gap-2">
              <Button
                disabled={confirmingId === booking.id}
                onClick={() => void handleConfirm(booking)}
              >
                Confirm
              </Button>
              <RejectDialog booking={booking} onDone={refresh} />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
