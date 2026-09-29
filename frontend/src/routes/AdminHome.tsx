import { useAuth } from '@/auth/AuthContext'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export function AdminHome() {
  const { user } = useAuth()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Welcome, {user?.full_name}</CardTitle>
        <CardDescription>
          Business, service, and provider management arrives in Section 10.
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        This is a placeholder admin home — it exists to prove the route, role guard, and
        layout work end-to-end.
      </CardContent>
    </Card>
  )
}
