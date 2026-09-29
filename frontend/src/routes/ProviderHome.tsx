import { useAuth } from '@/auth/AuthContext'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export function ProviderHome() {
  const { user } = useAuth()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Welcome, {user?.full_name}</CardTitle>
        <CardDescription>
          Your schedule and bookings arrive in Section 10.
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        This is a placeholder provider home — it exists to prove the route, role guard,
        and layout work end-to-end.
      </CardContent>
    </Card>
  )
}
