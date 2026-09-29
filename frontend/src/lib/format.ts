const uzsFormatter = new Intl.NumberFormat('uz-UZ', {
  style: 'currency',
  currency: 'UZS',
  maximumFractionDigits: 0,
})

/** `price` is the backend's Decimal-as-string (e.g. "150000.00"). */
export function formatUZS(price: string): string {
  return uzsFormatter.format(Number.parseFloat(price))
}

export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const remainder = minutes % 60
  if (hours === 0) return `${remainder} min`
  if (remainder === 0) return `${hours}h`
  return `${hours}h ${remainder}min`
}
