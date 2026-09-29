import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from './AuthContext'
import type { components } from '@/api/schema'

type Role = components['schemas']['RoleEnum']

const ROLE_HOME: Record<Role, string> = {
  customer: '/',
  provider: '/provider',
  admin: '/admin',
}

export function RequireRole({ role }: { role: Role }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return null
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  if (user.role !== role) {
    return <Navigate to={ROLE_HOME[user.role]} replace />
  }

  return <Outlet />
}
