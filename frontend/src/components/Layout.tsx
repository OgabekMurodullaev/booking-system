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

export function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <Link to="/" className="font-semibold">
              Booking System
            </Link>
            {user?.role === 'customer' && (
              <nav className="hidden items-center gap-4 text-sm sm:flex">
                <Link
                  to="/services"
                  className="text-muted-foreground hover:text-foreground"
                >
                  Services
                </Link>
                <Link
                  to="/bookings"
                  className="text-muted-foreground hover:text-foreground"
                >
                  My Bookings
                </Link>
              </nav>
            )}
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
                  {user.role === 'customer' && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem asChild className="sm:hidden">
                        <Link to="/services">Services</Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild className="sm:hidden">
                        <Link to="/bookings">My Bookings</Link>
                      </DropdownMenuItem>
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
