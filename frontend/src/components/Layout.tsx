import { Link, Outlet } from 'react-router'
import { useAuth } from '@/auth/AuthContext'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

function initials(name: string): string {
  return name
    .split(' ')
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

const NAV_LINKS: Record<string, { to: string; label: string }[]> = {
  customer: [
    { to: '/services', label: 'Services' },
    { to: '/bookings', label: 'My Bookings' },
  ],
  provider: [
    { to: '/provider', label: 'Schedule' },
    { to: '/provider/approvals', label: 'Approvals' },
    { to: '/provider/working-hours', label: 'Working Hours' },
    { to: '/provider/time-off', label: 'Time Off' },
  ],
  admin: [
    { to: '/admin', label: 'Dashboard' },
    { to: '/admin/services', label: 'Services' },
    { to: '/admin/providers', label: 'Providers' },
    { to: '/admin/bookings', label: 'Bookings' },
  ],
}

export function Layout() {
  const { user, logout } = useAuth()
  const navLinks = user ? (NAV_LINKS[user.role] ?? []) : []

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <Link to="/" className="font-semibold">
              Booking System
            </Link>
            <nav className="hidden items-center gap-4 text-sm sm:flex">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className="text-muted-foreground hover:text-foreground"
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>

          {user && (
            <div className="flex items-center gap-3">
              <span className="hidden text-sm text-muted-foreground sm:inline">
                {user.timezone}
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    className="h-9 w-9 rounded-full p-0"
                    aria-label="User menu"
                  >
                    <Avatar className="h-9 w-9">
                      <AvatarFallback>{initials(user.full_name)}</AvatarFallback>
                    </Avatar>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>
                    <div className="flex flex-col">
                      <span className="font-medium">{user.full_name}</span>
                      <span className="text-xs font-normal text-muted-foreground">
                        {user.email}
                      </span>
                      <span className="mt-1 text-xs font-normal text-muted-foreground sm:hidden">
                        {user.timezone}
                      </span>
                    </div>
                  </DropdownMenuLabel>
                  {navLinks.length > 0 && (
                    <>
                      <DropdownMenuSeparator />
                      {navLinks.map((link) => (
                        <DropdownMenuItem key={link.to} asChild className="sm:hidden">
                          <Link to={link.to}>{link.label}</Link>
                        </DropdownMenuItem>
                      ))}
                    </>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={() => void logout()}>
                    Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
