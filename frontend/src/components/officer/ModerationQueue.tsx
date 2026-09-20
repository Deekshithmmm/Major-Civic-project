import { useCallback, useEffect, useState } from 'react'

import AllegationBadge from '../AllegationBadge'
import ReportMedia from '../ReportMedia'
import { apiGet, apiPost, type FeedItem } from '../../lib/api'

/**
 * Pre-publication moderation (spec 2.3): nothing reaches the public feed until a moderator
 * approves it. Moderators check for identifiable bystanders, doxxing, obvious fabrication,
 * content that isn't a corruption report, and anything sub judice.
 */
export default function ModerationQueue() {
  const [queue, setQueue] = useState<FeedItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const refresh = useCallback(() => {
    apiGet<FeedItem[]>('/api/corruption/moderation/queue')
      .then(setQueue)
      .catch(() => setError('Could not load the moderation queue.'))
  }, [])

  useEffect(refresh, [refresh])

  async function decide(id: string, decision: 'approve' | 'reject') {
    setBusy(id)
    setError(null)
    try {
      await apiPost(`/api/corruption/moderation/${id}/${decision}`, {})
      refresh()
    } catch {
      setError('That decision could not be saved.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-semibold text-ink">Awaiting moderation ({queue.length})</h2>
        <p className="text-sm text-slate-600">
          Check for identifiable bystanders, doxxing, anything that isn’t a corruption report, and
          anything sub judice. Video is not face-blurred, so bystanders are your call.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      {queue.length === 0 ? (
        <p className="text-slate-600">Nothing waiting.</p>
      ) : (
        <ul className="space-y-3">
          {queue.map((item) => (
            <li key={item.id} className="card space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{item.accused_department}</p>
                  <p className="text-sm text-slate-700">{item.accused_designation}</p>
                  <p className="text-xs text-slate-600">
                    Area {item.geohash} · {new Date(item.created_at).toLocaleString()}
                  </p>
                </div>
                <AllegationBadge badge={item.public_status_badge} />
              </div>

              <ReportMedia
                mediaId={item.media_id}
                kind={item.media_kind}
                label={`Evidence submitted about ${item.accused_designation}, ${item.accused_department}`}
                className="max-h-64"
              />

              {item.description && <p className="text-sm text-slate-700">{item.description}</p>}

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-primary"
                  disabled={busy === item.id}
                  onClick={() => decide(item.id, 'approve')}
                >
                  Publish to feed
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={busy === item.id}
                  onClick={() => decide(item.id, 'reject')}
                >
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
