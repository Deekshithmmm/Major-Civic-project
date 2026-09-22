import type { ReactNode } from 'react'

/**
 * Loading, empty and error states, in one place so every page says the same thing the same way.
 * A bare "…" tells a reader nothing about whether the page is working.
 */

export function Loading({ label = 'Loading…', rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="animate-pulse rounded-lg border border-slate-200 bg-white p-4">
          <div className="h-4 w-1/3 rounded bg-slate-200" />
          <div className="mt-2 h-3 w-2/3 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  )
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string
  body?: string
  action?: ReactNode
}) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center">
      <p className="font-medium text-ink">{title}</p>
      {body && <p className="mx-auto mt-1 max-w-md text-sm text-slate-600">{body}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      {message}
    </p>
  )
}
