import { useCallback, useEffect, useState } from 'react'

import AllegationBadge from '../AllegationBadge'
import { apiGet, apiPost, type FeedItem, type PublicStatusBadge } from '../../lib/api'

const BADGES: { value: PublicStatusBadge; label: string }[] = [
  { value: 'unverified_allegation', label: 'Unverified allegation' },
  { value: 'under_investigation', label: 'Under investigation' },
  { value: 'action_taken', label: 'Action taken' },
  { value: 'dismissed', label: 'Dismissed' },
]

/**
 * Oversight-body side of Module 2: the status badge on a published report is moved by the body
 * that actually acts on it, so "Unverified allegation" only changes when something really has.
 */
export default function VigilancePanel() {
  const [items, setItems] = useState<FeedItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const refresh = useCallback(() => {
    apiGet<FeedItem[]>('/api/corruption/feed')
      .then(setItems)
      .catch(() => setError('Could not load published reports.'))
  }, [])

  useEffect(refresh, [refresh])

  async function setBadge(id: string, badge: PublicStatusBadge) {
    setBusy(id)
    setError(null)
    try {
      await apiPost(`/api/corruption/reports/${id}/status?badge=${badge}`)
      refresh()
    } catch {
      setError('That status could not be saved.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="font-semibold text-ink">Published reports ({items.length})</h2>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      {items.length === 0 ? (
        <p className="text-slate-600">Nothing published yet.</p>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.id} className="card flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-medium">{item.accused_department}</p>
                <p className="text-sm text-slate-700">{item.accused_designation}</p>
                <div className="mt-1">
                  <AllegationBadge badge={item.public_status_badge} />
                </div>
              </div>
              <div>
                <label htmlFor={`badge-${item.id}`} className="sr-only">
                  Set status for this report
                </label>
                <select
                  id={`badge-${item.id}`}
                  className="rounded-md border border-slate-300 px-2 py-2 text-sm"
                  value={item.public_status_badge}
                  disabled={busy === item.id}
                  onChange={(e) => setBadge(item.id, e.target.value as PublicStatusBadge)}
                >
                  {BADGES.map((b) => (
                    <option key={b.value} value={b.value}>
                      {b.label}
                    </option>
                  ))}
                </select>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
