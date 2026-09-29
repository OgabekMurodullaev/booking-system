import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { AuthProvider } from '@/auth/AuthContext'
import { RequireRole } from '@/auth/RequireRole'
import { Layout } from '@/components/Layout'
import { Toaster } from '@/components/ui/sonner'
import { Bookings as AdminBookings } from '@/routes/admin/Bookings'
import { Dashboard } from '@/routes/admin/Dashboard'
import { Providers as AdminProviders } from '@/routes/admin/Providers'
import { Services as AdminServices } from '@/routes/admin/Services'
import { BookingFlow } from '@/routes/BookingFlow'
import { CustomerHome } from '@/routes/CustomerHome'
import { Login } from '@/routes/Login'
import { MyBookings } from '@/routes/MyBookings'
import { Approvals } from '@/routes/provider/Approvals'
import { Schedule } from '@/routes/provider/Schedule'
import { TimeOff } from '@/routes/provider/TimeOff'
import { WorkingHours } from '@/routes/provider/WorkingHours'
import { Register } from '@/routes/Register'
import { Services } from '@/routes/Services'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            <Route element={<RequireRole role="customer" />}>
              <Route element={<Layout />}>
                <Route path="/" element={<CustomerHome />} />
                <Route path="/services" element={<Services />} />
                <Route path="/services/:serviceId/book" element={<BookingFlow />} />
                <Route path="/bookings" element={<MyBookings />} />
              </Route>
            </Route>

            <Route element={<RequireRole role="provider" />}>
              <Route element={<Layout />}>
                <Route path="/provider" element={<Schedule />} />
                <Route path="/provider/approvals" element={<Approvals />} />
                <Route path="/provider/working-hours" element={<WorkingHours />} />
                <Route path="/provider/time-off" element={<TimeOff />} />
              </Route>
            </Route>

            <Route element={<RequireRole role="admin" />}>
              <Route element={<Layout />}>
                <Route path="/admin" element={<Dashboard />} />
                <Route path="/admin/services" element={<AdminServices />} />
                <Route path="/admin/providers" element={<AdminProviders />} />
                <Route path="/admin/bookings" element={<AdminBookings />} />
              </Route>
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <Toaster />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
