import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { apiClient } from '@/api/client'
import { ApiError, unwrap } from '@/api/errors'
import type { components } from '@/api/schema'
import { useServices } from '@/hooks/useServices'
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
import { Textarea } from '@/components/ui/textarea'
import { formatDuration, formatUZS } from '@/lib/format'

type Service = components['schemas']['Service']

const serviceSchema = z.object({
  name: z.string().min(1, 'Required'),
  description: z.string().optional(),
  duration_minutes: z.coerce
    .number()
    .int()
    .min(5, 'Must be at least 5 minutes')
    .max(480, 'Must be at most 480 minutes')
    .refine((v) => v % 5 === 0, 'Must be a multiple of 5'),
  price: z.coerce.number().positive('Must be a positive number'),
  buffer_minutes: z.coerce.number().int().min(0).max(120),
})
type ServiceFormInput = z.input<typeof serviceSchema>
type ServiceFormValues = z.output<typeof serviceSchema>

function ServiceDialog({ service, onSaved }: { service?: Service; onSaved: () => void }) {
  const [open, setOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<ServiceFormInput, unknown, ServiceFormValues>({
    resolver: zodResolver(serviceSchema),
    defaultValues: service
      ? {
          name: service.name,
          description: service.description,
          duration_minutes: service.duration_minutes,
          price: Number.parseFloat(service.price),
          buffer_minutes: service.buffer_minutes,
        }
      : { buffer_minutes: 0 },
  })

  async function onSubmit(values: ServiceFormValues) {
    setIsSubmitting(true)
    try {
      const body = { ...values, price: values.price.toFixed(2) }
      if (service) {
        await unwrap(
          apiClient.PATCH('/api/v1/services/{id}/', {
            params: { path: { id: service.id } },
            body,
          }),
        )
        toast.success('Service updated.')
      } else {
        await unwrap(apiClient.POST('/api/v1/services/', { body }))
        toast.success('Service created.')
      }
      setOpen(false)
      reset()
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
        <Button
          variant={service ? 'outline' : 'default'}
          size={service ? 'sm' : 'default'}
        >
          {service ? 'Edit' : 'New service'}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{service ? 'Edit service' : 'New service'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="service-name">Name</Label>
            <Input id="service-name" {...register('name')} />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="service-description">Description</Label>
            <Textarea id="service-description" rows={2} {...register('description')} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="service-duration">Duration (min)</Label>
              <Input
                id="service-duration"
                type="number"
                step={5}
                {...register('duration_minutes')}
              />
              {errors.duration_minutes && (
                <p className="text-sm text-destructive">
                  {errors.duration_minutes.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="service-buffer">Buffer (min)</Label>
              <Input id="service-buffer" type="number" {...register('buffer_minutes')} />
              {errors.buffer_minutes && (
                <p className="text-sm text-destructive">
                  {errors.buffer_minutes.message}
                </p>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="service-price">Price (UZS)</Label>
            <Input id="service-price" type="number" step="0.01" {...register('price')} />
            {errors.price && (
              <p className="text-sm text-destructive">{errors.price.message}</p>
            )}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function Services() {
  const { data, isLoading, isError, refetch } = useServices()

  async function handleDeactivate(service: Service) {
    try {
      await unwrap(
        apiClient.DELETE('/api/v1/services/{id}/', {
          params: { path: { id: service.id } },
        }),
      )
      toast.success('Service deactivated.')
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
    return <p className="text-sm text-muted-foreground">Couldn&apos;t load services.</p>

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <ServiceDialog onSaved={() => void refetch()} />
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Duration</TableHead>
            <TableHead>Price</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(data?.results ?? []).map((service) => (
            <TableRow key={service.id}>
              <TableCell>{service.name}</TableCell>
              <TableCell>{formatDuration(service.duration_minutes)}</TableCell>
              <TableCell>{formatUZS(service.price)}</TableCell>
              <TableCell>{service.is_active ? 'Active' : 'Inactive'}</TableCell>
              <TableCell className="flex justify-end gap-2">
                <ServiceDialog service={service} onSaved={() => void refetch()} />
                {service.is_active && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleDeactivate(service)}
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
