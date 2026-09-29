import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'
import { ApiError } from '@/api/errors'
import type { components } from '@/api/schema'
import { useAuth } from '@/auth/AuthContext'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address.'),
  password: z.string().min(1, 'Password is required.'),
})
type LoginFormValues = z.infer<typeof loginSchema>

const ROLE_HOME: Record<components['schemas']['RoleEnum'], string> = {
  customer: '/',
  provider: '/provider',
  admin: '/admin',
}

interface DemoAccount {
  label: string
  email: string
  password: string
}

function readDemoAccounts(): DemoAccount[] {
  const candidates: Array<[string, string | undefined, string | undefined]> = [
    [
      'Customer',
      import.meta.env.VITE_DEMO_CUSTOMER_EMAIL,
      import.meta.env.VITE_DEMO_CUSTOMER_PASSWORD,
    ],
    [
      'Provider',
      import.meta.env.VITE_DEMO_PROVIDER_EMAIL,
      import.meta.env.VITE_DEMO_PROVIDER_PASSWORD,
    ],
    [
      'Admin',
      import.meta.env.VITE_DEMO_ADMIN_EMAIL,
      import.meta.env.VITE_DEMO_ADMIN_PASSWORD,
    ],
  ]
  return candidates
    .filter((entry): entry is [string, string, string] => Boolean(entry[1] && entry[2]))
    .map(([label, email, password]) => ({ label, email, password }))
}

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const demoAccounts = readDemoAccounts()

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) })

  async function onSubmit(values: LoginFormValues) {
    setIsSubmitting(true)
    try {
      const user = await login(values.email, values.password)
      const state = location.state as { from?: { pathname?: string } } | null
      navigate(state?.from?.pathname ?? ROLE_HOME[user.role], { replace: true })
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

  function fillDemoAndSubmit(account: DemoAccount) {
    setValue('email', account.email)
    setValue('password', account.password)
    void handleSubmit(onSubmit)()
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Log in</CardTitle>
          <CardDescription>Welcome back.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <div className="space-y-2">
              <Label htmlFor="login-email">Email</Label>
              <Input
                id="login-email"
                type="email"
                autoComplete="email"
                {...register('email')}
              />
              {errors.email && (
                <p className="text-sm text-destructive">{errors.email.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="login-password">Password</Label>
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                {...register('password')}
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? 'Logging in...' : 'Log in'}
            </Button>
          </form>

          {demoAccounts.length > 0 && (
            <div className="mt-6 space-y-2 border-t border-border pt-4">
              <p className="text-center text-sm text-muted-foreground">
                Or try a demo account
              </p>
              <div className="flex flex-col gap-2">
                {demoAccounts.map((account) => (
                  <Button
                    key={account.label}
                    type="button"
                    variant="outline"
                    onClick={() => fillDemoAndSubmit(account)}
                  >
                    Try as {account.label}
                  </Button>
                ))}
              </div>
            </div>
          )}

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{' '}
            <Link to="/register" className="text-accent-text hover:underline">
              Register
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
