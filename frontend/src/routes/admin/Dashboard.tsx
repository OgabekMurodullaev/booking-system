import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { format } from 'date-fns'
import { useStats } from '@/hooks/useStats'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

export function Dashboard() {
  const { data, isLoading, isError } = useStats()

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-72" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <p className="text-sm text-muted-foreground">Couldn&apos;t load dashboard stats.</p>
    )
  }

  const chartData = data.bookings_per_day.map((row) => ({
    date: format(new Date(row.date), 'd MMM'),
    count: row.count,
  }))

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Today's bookings" value={String(data.today_bookings_count)} />
        <StatCard label="Cancellation rate (14d)" value={`${data.cancellation_rate}%`} />
        <StatCard
          label="Late cancellations (14d)"
          value={String(data.late_cancellation_count)}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Bookings per day (last 14 days)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" fontSize={12} stroke="var(--muted-foreground)" />
                <YAxis
                  allowDecimals={false}
                  fontSize={12}
                  stroke="var(--muted-foreground)"
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--popover)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)',
                  }}
                />
                <Bar dataKey="count" fill="var(--primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Provider utilization (last 14 days)</CardTitle>
          <CardDescription>Booked minutes as a share of working minutes.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Provider</TableHead>
                <TableHead className="text-right">Utilization</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.provider_utilization.map((row) => (
                <TableRow key={row.provider_id}>
                  <TableCell>{row.provider_name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {row.utilization_percent}%
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
