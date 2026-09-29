import { useState } from 'react'
import { toZonedTime } from 'date-fns-tz'
import { useAuth } from '@/auth/AuthContext'
import { useBookingsList } from '@/hooks/useBookings'
import { useProviders, useServices } from '@/hooks/useServices'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatUZS } from '@/lib/format'

type StatusFilter = 'all' | 'pending' | 'confirmed' | 'cancelled' | 'completed'

function timeLabel(iso: string, timeZone: string): string {
  return toZonedTime(new Date(iso), timeZone).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function Bookings() {
  const { user } = useAuth()
  const timeZone = user?.timezone ?? 'UTC'
  const { data: providersPage } = useProviders()
  const { data: servicesPage } = useServices()

  const [status, setStatus] = useState<StatusFilter>('all')
  const [providerId, setProviderId] = useState<string>('all')
  const [serviceId, setServiceId] = useState<string>('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)

  const { data, isLoading, isError } = useBookingsList({
    status: status === 'all' ? undefined : status,
    provider: providerId === 'all' ? undefined : Number(providerId),
    service: serviceId === 'all' ? undefined : Number(serviceId),
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    page,
  })

  function resetToFirstPage<T>(setter: (value: T) => void) {
    return (value: T) => {
      setPage(1)
      setter(value)
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="space-y-2">
          <Label>Status</Label>
          <Select
            value={status}
            onValueChange={resetToFirstPage(setStatus as (v: string) => void)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="confirmed">Confirmed</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Provider</Label>
          <Select value={providerId} onValueChange={resetToFirstPage(setProviderId)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              {(providersPage?.results ?? []).map((provider) => (
                <SelectItem key={provider.id} value={String(provider.id)}>
                  {provider.user.full_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Service</Label>
          <Select value={serviceId} onValueChange={resetToFirstPage(setServiceId)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              {(servicesPage?.results ?? []).map((service) => (
                <SelectItem key={service.id} value={String(service.id)}>
                  {service.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-2">
            <Label>From</Label>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => resetToFirstPage(setDateFrom)(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>To</Label>
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => resetToFirstPage(setDateTo)(e.target.value)}
            />
          </div>
        </div>
      </div>

      {isLoading && <Skeleton className="h-64" />}
      {isError && (
        <p className="text-sm text-muted-foreground">Couldn&apos;t load bookings.</p>
      )}

      {!isLoading && !isError && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Customer</TableHead>
                <TableHead>Service</TableHead>
                <TableHead>Time</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Price</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.results ?? []).map((booking) => (
                <TableRow key={booking.id}>
                  <TableCell>{booking.customer_name}</TableCell>
                  <TableCell>{booking.service_name}</TableCell>
                  <TableCell>{timeLabel(booking.start, timeZone)}</TableCell>
                  <TableCell>
                    <StatusBadge status={booking.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    {formatUZS(booking.price_snapshot)}
                  </TableCell>
                </TableRow>
              ))}
              {(data?.results ?? []).length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="text-center text-sm text-muted-foreground"
                  >
                    No bookings match these filters.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          <div className="flex items-center justify-between">
            <Button
              variant="outline"
              size="sm"
              disabled={!data?.previous}
              onClick={() => setPage((p) => p - 1)}
            >
              &larr; Previous
            </Button>
            <span className="text-sm text-muted-foreground">Page {page}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={!data?.next}
              onClick={() => setPage((p) => p + 1)}
            >
              Next &rarr;
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
