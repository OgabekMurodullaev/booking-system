import { useAuth } from '@/auth/AuthContext'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export function CustomerHome() {
  const { user } = useAuth()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Welcome, {user?.full_name}</CardTitle>
        <CardDescription>
          Browsing and booking services arrives in Section 9.
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        This is a placeholder customer home — it exists to prove the route, role guard,
        and layout work end-to-end.
      </CardContent>
    </Card>
  )
}
