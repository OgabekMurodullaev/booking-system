import { Link } from 'react-router'
import { useServices } from '@/hooks/useServices'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDuration, formatUZS } from '@/lib/format'

export function Services() {
  const { data, isLoading, isError } = useServices()

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-40 rounded-lg" />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <p className="text-sm text-muted-foreground">
        Couldn&apos;t load services right now. Please try again in a moment.
      </p>
    )
  }

  const services = data?.results ?? []

  if (services.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No services are available to book yet.
      </p>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {services.map((service) => (
        <Link key={service.id} to={`/services/${service.id}/book`}>
          <Card className="h-full transition-colors hover:border-primary">
            <CardHeader>
              <CardTitle>{service.name}</CardTitle>
              <CardDescription>
                {formatDuration(service.duration_minutes)} &middot;{' '}
                {formatUZS(service.price)}
              </CardDescription>
            </CardHeader>
            {service.description && (
              <CardContent className="text-sm text-muted-foreground">
                {service.description}
              </CardContent>
            )}
          </Card>
        </Link>
      ))}
    </div>
  )
}
