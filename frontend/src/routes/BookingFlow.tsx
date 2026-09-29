import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { addDays, format } from 'date-fns'
import { toZonedTime } from 'date-fns-tz'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'
import { apiClient } from '@/api/client'
import { ApiError, unwrap } from '@/api/errors'
import type { components } from '@/api/schema'
import { useAvailability } from '@/hooks/useAvailability'
import { useProviders, useService } from '@/hooks/useServices'
import { generateIdempotencyKey } from '@/lib/idempotency'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/StatusBadge'
import { cn } from '@/lib/utils'
import { formatDuration, formatUZS } from '@/lib/format'

type Slot = components['schemas']['Slot']
type BookingDetail = components['schemas']['BookingDetail']

const DAYS_AHEAD = 14
type Bucket = 'Morning' | 'Afternoon' | 'Evening'

function todayISO(): string {
  return format(new Date(), 'yyyy-MM-dd')
}

function bucketForHour(hour: number): Bucket {
  if (hour < 12) return 'Morning'
  if (hour < 18) return 'Afternoon'
  return 'Evening'
}

function timeLabel(iso: string, timeZone: string): string {
  return toZonedTime(new Date(iso), timeZone).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function BookingFlow() {
  const { serviceId } = useParams<{ serviceId: string }>()
  const serviceIdNum = Number(serviceId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: service, isLoading: serviceLoading } = useService(serviceIdNum)
  const dateFrom = useMemo(() => todayISO(), [])
  const dateTo = useMemo(
    () => format(addDays(new Date(), DAYS_AHEAD - 1), 'yyyy-MM-dd'),
    [],
  )
  const {
    data: availability,
    isLoading: availabilityLoading,
    isError: availabilityError,
  } = useAvailability(serviceIdNum, dateFrom, dateTo)
  const { data: providersPage } = useProviders()

  const [selectedProviderId, setSelectedProviderId] = useState<number | null>(null)
  const [pickedDate, setPickedDate] = useState<string | null>(null)
  const [hold, setHold] = useState<BookingDetail | null>(null)
  const [nowTick, setNowTick] = useState(() => Date.now())
  const [alternatives, setAlternatives] = useState<Slot[]>([])
  const [isCreatingHold, setIsCreatingHold] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [confirmResult, setConfirmResult] = useState<BookingDetail | null>(null)

  const availableProviderIds = useMemo(() => {
    const ids = new Set<number>()
    for (const day of availability?.dates ?? []) {
      for (const slot of day.slots) {
        for (const id of slot.provider_ids) ids.add(id)
      }
    }
    return ids
  }, [availability])

  const providerOptions = useMemo(
    () =>
      (providersPage?.results ?? []).filter((provider) =>
        availableProviderIds.has(provider.id),
      ),
    [providersPage, availableProviderIds],
  )

  const filteredDates = useMemo(() => {
    if (!availability) return []
    return availability.dates.map((day) => ({
      date: day.date,
      slots: selectedProviderId
        ? day.slots.filter((slot) => slot.provider_ids.includes(selectedProviderId))
        : day.slots,
    }))
  }, [availability, selectedProviderId])

  // Derived, not synced via effect: a picked date stays selected as long as it still
  // has slots (e.g. after a provider switch); otherwise fall back to the first day
  // that has any.
  const selectedDate =
    (pickedDate &&
      filteredDates.find((day) => day.date === pickedDate && day.slots.length > 0)
        ?.date) ??
    filteredDates.find((day) => day.slots.length > 0)?.date ??
    null

  const activeDaySlots = useMemo(
    () => filteredDates.find((day) => day.date === selectedDate)?.slots ?? [],
    [filteredDates, selectedDate],
  )

  const grouped = useMemo(() => {
    const timeZone = availability?.timezone ?? 'UTC'
    const buckets: Record<Bucket, Slot[]> = { Morning: [], Afternoon: [], Evening: [] }
    for (const slot of activeDaySlots) {
      const hour = toZonedTime(new Date(slot.start), timeZone).getHours()
      buckets[bucketForHour(hour)].push(slot)
    }
    return buckets
  }, [activeDaySlots, availability?.timezone])

  // Ticks the clock every second while a hold is active; expiry itself is derived
  // below rather than tracked as its own state (React's own guidance: prefer
  // computing during render over syncing derived state via an effect).
  useEffect(() => {
    if (!hold) return
    const interval = setInterval(() => setNowTick(Date.now()), 1000)
    return () => clearInterval(interval)
  }, [hold])

  const secondsLeft = hold?.expires_at
    ? Math.max(0, Math.round((new Date(hold.expires_at).getTime() - nowTick) / 1000))
    : null
  const isHoldExpired = hold !== null && secondsLeft === 0

  useEffect(() => {
    if (isHoldExpired) {
      void queryClient.invalidateQueries({ queryKey: ['availability', serviceIdNum] })
    }
  }, [isHoldExpired, queryClient, serviceIdNum])

  async function attemptHold(slot: Slot) {
    setIsCreatingHold(true)
    setAlternatives([])
    try {
      const provider =
        selectedProviderId && slot.provider_ids.includes(selectedProviderId)
          ? selectedProviderId
          : undefined
      const booking = await unwrap(
        apiClient.POST('/api/v1/bookings/', {
          body: { service: serviceIdNum, provider, start: slot.start },
          headers: { 'Idempotency-Key': generateIdempotencyKey() },
        }),
      )
      setHold(booking)
    } catch (error) {
      if (error instanceof ApiError && error.code === 'slot_unavailable') {
        const alts = (error.details?.alternatives as Slot[] | undefined) ?? []
        setAlternatives(alts)
        toast.error('This time was just taken.')
        void queryClient.invalidateQueries({ queryKey: ['availability', serviceIdNum] })
      } else {
        toast.error(
          error instanceof ApiError
            ? error.message
            : 'Something went wrong. Please try again.',
        )
      }
    } finally {
      setIsCreatingHold(false)
    }
  }

  async function handleConfirm() {
    if (!hold) return
    setIsSubmitting(true)
    try {
      const updated = await unwrap(
        apiClient.POST('/api/v1/bookings/{id}/submit/', {
          params: { path: { id: hold.id } },
        }),
      )
      setConfirmResult(updated)
      setHold(null)
      void queryClient.invalidateQueries({ queryKey: ['bookings'] })
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

  if (serviceLoading || availabilityLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    )
  }

  if (availabilityError || !availability || !service) {
    return (
      <p className="text-sm text-muted-foreground">
        Couldn&apos;t load this service. Please try again.
      </p>
    )
  }

  if (confirmResult) {
    const isConfirmed = confirmResult.status === 'confirmed'
    return (
      <Card className="mx-auto max-w-md">
        <CardHeader>
          <CardTitle>{isConfirmed ? "You're booked!" : 'Waiting for approval'}</CardTitle>
          <CardDescription>
            {isConfirmed
              ? 'Your booking is confirmed.'
              : 'The provider needs to confirm this booking before it is final.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <StatusBadge status={confirmResult.status} />
          <Button onClick={() => navigate('/bookings')}>Go to My Bookings</Button>
        </CardContent>
      </Card>
    )
  }

  if (hold && !isHoldExpired) {
    return (
      <Card className="mx-auto max-w-md">
        <CardHeader>
          <CardTitle>Confirm your booking</CardTitle>
          <CardDescription>
            {service.name} &middot; {timeLabel(hold.start, availability.timezone)} (
            {availability.timezone} time)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm">
            Price: <span className="font-medium">{formatUZS(hold.price_snapshot)}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            This hold expires in{' '}
            <span className="font-medium tabular-nums text-foreground">
              {String(Math.floor((secondsLeft ?? 0) / 60)).padStart(2, '0')}:
              {String((secondsLeft ?? 0) % 60).padStart(2, '0')}
            </span>
          </p>
          <div className="flex gap-2">
            <Button onClick={() => void handleConfirm()} disabled={isSubmitting}>
              {isSubmitting ? 'Confirming...' : 'Confirm booking'}
            </Button>
            <Button variant="outline" onClick={() => setHold(null)}>
              Choose a different time
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>{service.name}</CardTitle>
          <CardDescription>
            {formatDuration(service.duration_minutes)} &middot; {formatUZS(service.price)}
          </CardDescription>
        </CardHeader>
      </Card>

      {isHoldExpired && (
        <div className="flex items-center justify-between rounded-md bg-warning-bg px-4 py-3 text-sm text-warning">
          <span>Hold expired &mdash; please pick a time again.</span>
          <Button size="sm" variant="outline" onClick={() => setHold(null)}>
            Dismiss
          </Button>
        </div>
      )}

      {alternatives.length > 0 && (
        <div className="space-y-2 rounded-md bg-warning-bg px-4 py-3">
          <p className="text-sm text-warning">
            This time was just taken. Try one of these instead:
          </p>
          <div className="flex flex-wrap gap-2">
            {alternatives.map((alt) => (
              <Button
                key={alt.start}
                size="sm"
                variant="outline"
                onClick={() => void attemptHold(alt)}
                disabled={isCreatingHold}
              >
                {timeLabel(alt.start, availability.timezone)}
              </Button>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        <span className="text-sm font-medium">Provider</span>
        <Select
          value={selectedProviderId ? String(selectedProviderId) : 'any'}
          onValueChange={(value) =>
            setSelectedProviderId(value === 'any' ? null : Number(value))
          }
        >
          <SelectTrigger className="w-full sm:w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="any">Any available</SelectItem>
            {providerOptions.map((provider) => (
              <SelectItem key={provider.id} value={String(provider.id)}>
                {provider.user.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <span className="text-sm font-medium">Date</span>
        <div className="flex gap-2 overflow-x-auto pb-2">
          {filteredDates.map((day) => {
            const disabled = day.slots.length === 0
            const isSelected = day.date === selectedDate
            return (
              <button
                key={day.date}
                type="button"
                disabled={disabled}
                onClick={() => setPickedDate(day.date)}
                className={cn(
                  'flex min-w-16 flex-col items-center rounded-md border px-3 py-2 text-sm',
                  disabled && 'cursor-not-allowed opacity-40',
                  isSelected
                    ? 'border-primary bg-accent text-accent-text'
                    : 'border-border',
                )}
              >
                <span className="text-xs text-muted-foreground">
                  {format(new Date(day.date), 'EEE')}
                </span>
                <span className="font-medium">{format(new Date(day.date), 'd MMM')}</span>
              </button>
            )
          })}
        </div>
      </div>

      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Times shown in {availability.timezone} time
        </p>
        {(['Morning', 'Afternoon', 'Evening'] as const).map((bucket) =>
          grouped[bucket].length > 0 ? (
            <div key={bucket} className="space-y-2">
              <span className="text-sm font-medium">{bucket}</span>
              <div className="flex flex-wrap gap-2">
                {grouped[bucket].map((slot) => (
                  <Button
                    key={slot.start}
                    variant="outline"
                    disabled={isCreatingHold}
                    onClick={() => void attemptHold(slot)}
                  >
                    {timeLabel(slot.start, availability.timezone)}
                  </Button>
                ))}
              </div>
            </div>
          ) : null,
        )}
        {activeDaySlots.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No free times on this day. Try another date.
          </p>
        )}
      </div>

      <Link
        to="/services"
        className="inline-block text-sm text-accent-text hover:underline"
      >
        &larr; Back to services
      </Link>
    </div>
  )
}
