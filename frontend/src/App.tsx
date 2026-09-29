import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { AuthProvider } from '@/auth/AuthContext'
import { RequireRole } from '@/auth/RequireRole'
import { Layout } from '@/components/Layout'
import { Toaster } from '@/components/ui/sonner'
import { AdminHome } from '@/routes/AdminHome'
import { BookingFlow } from '@/routes/BookingFlow'
import { CustomerHome } from '@/routes/CustomerHome'
import { Login } from '@/routes/Login'
import { MyBookings } from '@/routes/MyBookings'
import { ProviderHome } from '@/routes/ProviderHome'
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
                <Route path="/provider" element={<ProviderHome />} />
              </Route>
            </Route>

            <Route element={<RequireRole role="admin" />}>
              <Route element={<Layout />}>
                <Route path="/admin" element={<AdminHome />} />
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
