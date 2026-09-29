import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toZonedTime } from 'date-fns-tz'
import { toast } from 'sonner'
import { apiClient } from '@/api/client'
import { ApiError, unwrap } from '@/api/errors'
import { useAuth } from '@/auth/AuthContext'
import { useTimeOff } from '@/hooks/useTimeOff'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'

function timeLabel(iso: string, timeZone: string): string {
  return toZonedTime(new Date(iso), timeZone).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function TimeOff() {
  const { user } = useAuth()
  const timeZone = user?.timezone ?? 'UTC'
  const providerId = user?.provider_id ?? null
  const queryClient = useQueryClient()
  const { data, isLoading } = useTimeOff(providerId)

  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [reason, setReason] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['time-off', providerId] })
  }

  async function handleCreate() {
    if (providerId === null || !start || !end) return
    setIsSubmitting(true)
    try {
      await unwrap(
        apiClient.POST('/api/v1/providers/{provider_id}/time-off/', {
          params: { path: { provider_id: providerId } },
          body: {
            start: new Date(start).toISOString(),
            end: new Date(end).toISOString(),
            reason,
          },
        }),
      )
      toast.success('Time off added.')
      setStart('')
      setEnd('')
      setReason('')
      refresh()
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

  async function handleDelete(id: number) {
    if (providerId === null) return
    try {
      await unwrap(
        apiClient.DELETE('/api/v1/providers/{provider_id}/time-off/{id}/', {
          params: { path: { provider_id: providerId, id } },
        }),
      )
      toast.success('Time off removed.')
      refresh()
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Something went wrong. Please try again.',
      )
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-4 py-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="timeoff-start">Start</Label>
              <Input
                id="timeoff-start"
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="timeoff-end">End</Label>
              <Input
                id="timeoff-end"
                type="datetime-local"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="timeoff-reason">Reason (optional)</Label>
            <Textarea
              id="timeoff-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
            />
          </div>
          <Button
            disabled={isSubmitting || !start || !end}
            onClick={() => void handleCreate()}
          >
            {isSubmitting ? 'Adding...' : 'Add time off'}
          </Button>
        </CardContent>
      </Card>

      {isLoading ? (
        <Skeleton className="h-32" />
      ) : (
        <div className="space-y-3">
          {(data?.results ?? []).length === 0 && (
            <p className="text-sm text-muted-foreground">No time off recorded.</p>
          )}
          {(data?.results ?? []).map((entry) => (
            <Card key={entry.id}>
              <CardContent className="flex items-center justify-between gap-4 py-4">
                <div>
                  <p className="text-sm font-medium">
                    {timeLabel(entry.start, timeZone)} &ndash;{' '}
                    {timeLabel(entry.end, timeZone)}
                  </p>
                  {entry.reason && (
                    <p className="text-sm text-muted-foreground">{entry.reason}</p>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void handleDelete(entry.id)}
                >
                  Remove
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
