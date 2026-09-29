import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiClient } from '@/api/client'
import { ApiError, unwrap } from '@/api/errors'
import { useAuth } from '@/auth/AuthContext'
import { useWorkingHours } from '@/hooks/useWorkingHours'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'

const WEEKDAY_LABELS = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
]

interface Interval {
  start_time: string
  end_time: string
}

type IntervalsByWeekday = Interval[][]

function hasOverlap(intervals: Interval[]): boolean {
  const sorted = [...intervals].sort((a, b) => a.start_time.localeCompare(b.start_time))
  for (let i = 1; i < sorted.length; i++) {
    const prev = sorted[i - 1]
    const cur = sorted[i]
    if (prev && cur && cur.start_time < prev.end_time) return true
  }
  return false
}

export function WorkingHours() {
  const { user } = useAuth()
  const providerId = user?.provider_id ?? null
  const queryClient = useQueryClient()
  const { data, isLoading } = useWorkingHours(providerId)

  const [byWeekday, setByWeekday] = useState<IntervalsByWeekday>(() =>
    Array.from({ length: 7 }, () => []),
  )
  const [isSaving, setIsSaving] = useState(false)
  // Seed the editable local copy from the fetched data exactly once per provider —
  // adjusted during render (React's own documented pattern for this), not via an
  // effect. Keyed on providerId rather than the `data` object reference: a background
  // refetch (e.g. window focus) returns a new object with the same content, which
  // would otherwise silently wipe in-progress local edits on every refetch.
  const [seededForProvider, setSeededForProvider] = useState<number | null>(null)
  if (data && providerId !== null && seededForProvider !== providerId) {
    setSeededForProvider(providerId)
    const grouped: IntervalsByWeekday = Array.from({ length: 7 }, () => [])
    for (const wh of data) {
      grouped[wh.weekday]?.push({
        start_time: wh.start_time.slice(0, 5),
        end_time: wh.end_time.slice(0, 5),
      })
    }
    setByWeekday(grouped)
  }

  function addInterval(weekday: number) {
    setByWeekday((current) =>
      current.map((intervals, i) =>
        i === weekday
          ? [...intervals, { start_time: '09:00', end_time: '17:00' }]
          : intervals,
      ),
    )
  }

  function removeInterval(weekday: number, index: number) {
    setByWeekday((current) =>
      current.map((intervals, i) =>
        i === weekday ? intervals.filter((_, j) => j !== index) : intervals,
      ),
    )
  }

  function updateInterval(
    weekday: number,
    index: number,
    field: keyof Interval,
    value: string,
  ) {
    setByWeekday((current) =>
      current.map((intervals, i) =>
        i === weekday
          ? intervals.map((interval, j) =>
              j === index ? { ...interval, [field]: value } : interval,
            )
          : intervals,
      ),
    )
  }

  const overlapErrors = byWeekday.map((intervals) => hasOverlap(intervals))
  const invalidOrderErrors = byWeekday.map((intervals) =>
    intervals.some((interval) => interval.start_time >= interval.end_time),
  )
  const hasAnyError = overlapErrors.some(Boolean) || invalidOrderErrors.some(Boolean)

  async function handleSave() {
    if (providerId === null || hasAnyError) return
    setIsSaving(true)
    try {
      const entries = byWeekday.flatMap((intervals, weekday) =>
        intervals.map((interval) => ({ weekday, ...interval })),
      )
      await unwrap(
        apiClient.PUT('/api/v1/providers/{provider_id}/working-hours/', {
          params: { path: { provider_id: providerId } },
          body: entries,
        }),
      )
      toast.success('Working hours saved.')
      void queryClient.invalidateQueries({ queryKey: ['working-hours', providerId] })
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Something went wrong. Please try again.',
      )
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading || providerId === null) {
    return <Skeleton className="h-96" />
  }

  return (
    <div className="space-y-6">
      {WEEKDAY_LABELS.map((label, weekday) => (
        <div key={label} className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{label}</span>
            <Button variant="outline" size="sm" onClick={() => addInterval(weekday)}>
              Add interval
            </Button>
          </div>
          {byWeekday[weekday]?.length === 0 && (
            <p className="text-xs text-muted-foreground">Not working this day.</p>
          )}
          {byWeekday[weekday]?.map((interval, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                type="time"
                value={interval.start_time}
                onChange={(e) =>
                  updateInterval(weekday, index, 'start_time', e.target.value)
                }
                className="w-32"
              />
              <span className="text-muted-foreground">to</span>
              <Input
                type="time"
                value={interval.end_time}
                onChange={(e) =>
                  updateInterval(weekday, index, 'end_time', e.target.value)
                }
                className="w-32"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeInterval(weekday, index)}
              >
                Remove
              </Button>
            </div>
          ))}
          {(overlapErrors[weekday] || invalidOrderErrors[weekday]) && (
            <p className="text-sm text-destructive">
              {overlapErrors[weekday]
                ? 'Intervals overlap.'
                : 'Each interval must end after it starts.'}
            </p>
          )}
        </div>
      ))}

      <Button disabled={isSaving || hasAnyError} onClick={() => void handleSave()}>
        {isSaving ? 'Saving...' : 'Save working hours'}
      </Button>
    </div>
  )
}
