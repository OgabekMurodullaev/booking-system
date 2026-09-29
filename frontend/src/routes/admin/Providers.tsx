import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { apiClient } from '@/api/client'
import { ApiError, unwrap } from '@/api/errors'
import type { components } from '@/api/schema'
import { useProviders, useServices } from '@/hooks/useServices'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type Provider = components['schemas']['Provider']

function ServiceCheckboxes({
  selected,
  onChange,
}: {
  selected: number[]
  onChange: (ids: number[]) => void
}) {
  const { data } = useServices()
  const services = (data?.results ?? []).filter((service) => service.is_active)

  function toggle(id: number) {
    onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id])
  }

  return (
    <div className="space-y-1">
      {services.map((service) => (
        <label key={service.id} className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={selected.includes(service.id)}
            onChange={() => toggle(service.id)}
          />
          {service.name}
        </label>
      ))}
    </div>
  )
}

const createSchema = z.object({
  email: z.string().email('Enter a valid email address.'),
  full_name: z.string().min(1, 'Required'),
  password: z.string().min(8, 'Password must be at least 8 characters.'),
})
type CreateFormValues = z.infer<typeof createSchema>

function CreateProviderDialog({ onSaved }: { onSaved: () => void }) {
  const [open, setOpen] = useState(false)
  const [serviceIds, setServiceIds] = useState<number[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<CreateFormValues>({ resolver: zodResolver(createSchema) })

  async function onSubmit(values: CreateFormValues) {
    setIsSubmitting(true)
    try {
      await unwrap(
        apiClient.POST('/api/v1/providers/', {
          body: { ...values, service_ids: serviceIds },
        }),
      )
      toast.success('Provider created.')
      setOpen(false)
      reset()
      setServiceIds([])
      onSaved()
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.code === 'validation_error' &&
        error.details
      ) {
        for (const [field, messages] of Object.entries(error.details)) {
          if (field === 'email' && Array.isArray(messages)) {
            setError('email', { message: String(messages[0]) })
          }
        }
      } else {
        toast.error(
          error instanceof ApiError
            ? error.message
            : 'Something went wrong. Please try again.',
        )
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>New provider</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New provider</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="provider-name">Full name</Label>
            <Input id="provider-name" {...register('full_name')} />
            {errors.full_name && (
              <p className="text-sm text-destructive">{errors.full_name.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="provider-email">Email</Label>
            <Input id="provider-email" type="email" {...register('email')} />
            {errors.email && (
              <p className="text-sm text-destructive">{errors.email.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="provider-password">Password</Label>
            <Input id="provider-password" type="password" {...register('password')} />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label>Services offered</Label>
            <ServiceCheckboxes selected={serviceIds} onChange={setServiceIds} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Creating...' : 'Create provider'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function EditServicesDialog({
  provider,
  onSaved,
}: {
  provider: Provider
  onSaved: () => void
}) {
  const [open, setOpen] = useState(false)
  const [serviceIds, setServiceIds] = useState<number[]>(
    provider.services.map((s) => s.id),
  )
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSave() {
    setIsSubmitting(true)
    try {
      await unwrap(
        apiClient.PATCH('/api/v1/providers/{id}/', {
          params: { path: { id: provider.id } },
          body: { service_ids: serviceIds },
        }),
      )
      toast.success('Services updated.')
      setOpen(false)
      onSaved()
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

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Edit services
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Services for {provider.user.full_name}</DialogTitle>
        </DialogHeader>
        <ServiceCheckboxes selected={serviceIds} onChange={setServiceIds} />
        <DialogFooter>
          <Button disabled={isSubmitting} onClick={() => void handleSave()}>
            {isSubmitting ? 'Saving...' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function Providers() {
  const { data, isLoading, isError, refetch } = useProviders()

  async function handleDeactivate(provider: Provider) {
    try {
      await unwrap(
        apiClient.PATCH('/api/v1/providers/{id}/', {
          params: { path: { id: provider.id } },
          body: { is_active: false },
        }),
      )
      toast.success('Provider deactivated.')
      void refetch()
    } catch (error) {
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Something went wrong. Please try again.',
      )
    }
  }

  if (isLoading) return <Skeleton className="h-64" />
  if (isError)
    return <p className="text-sm text-muted-foreground">Couldn&apos;t load providers.</p>

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <CreateProviderDialog onSaved={() => void refetch()} />
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Services</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(data?.results ?? []).map((provider) => (
            <TableRow key={provider.id}>
              <TableCell>{provider.user.full_name}</TableCell>
              <TableCell>{provider.user.email}</TableCell>
              <TableCell>
                {provider.services.map((s) => s.name).join(', ') || '—'}
              </TableCell>
              <TableCell>{provider.is_active ? 'Active' : 'Inactive'}</TableCell>
              <TableCell className="flex justify-end gap-2">
                <EditServicesDialog provider={provider} onSaved={() => void refetch()} />
                {provider.is_active && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleDeactivate(provider)}
                  >
                    Deactivate
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
