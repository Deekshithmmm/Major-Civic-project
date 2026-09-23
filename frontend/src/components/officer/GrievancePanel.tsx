import { useCallback, useEffect, useState } from 'react'

import { EmptyState } from '../Feedback'
import { apiGet, apiPost, type GrievanceQueueItem, type ReplyQueueItem } from '../../lib/api'

/**
 * The Grievance Officer's desk: complaints asking for a report to come down, and replies from
 * the offices reports concern, waiting to be verified.
 *
 * Both queues are ordered oldest-first and show the statutory deadline against each row, because
 * the thing this panel exists to prevent is a complaint quietly ageing past fifteen days.
 */
export default function GrievancePanel() {
  const [grievances, setGrievances] = useState<GrievanceQueueItem[]>([])
  const [replies, setReplies] = useState<ReplyQueueItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [notes, setNotes] = useState<Record<string, string>>({})

  const refresh = useCallback(() => {
    apiGet<GrievanceQueueItem[]>('/api/corruption/grievances/queue')
      .then(setGrievances)
      .catch(() => setError('Could not load the grievance queue.'))
    apiGet<ReplyQueueItem[]>('/api/corruption/replies/queue')
      .then(setReplies)
      .catch(() => undefined)
  }, [])

  useEffect(refresh, [refresh])

  async function decide(id: string, uphold: boolean) {
    const note = (notes[id] ?? '').trim()
    if (note.length < 10) {
      setError('A decision needs a reason of at least 10 characters. It is sent to the complainant.')
      return
    }
    setBusy(id)
    setError(null)
    try {
      await apiPost(`/api/corruption/grievances/${id}/decide`, { uphold, note })
      refresh()
    } catch {
      setError('That decision could not be saved.')
    } finally {
      setBusy(null)
    }
  }

  async function decideReply(id: string, publish: boolean) {
    setBusy(id)
    setError(null)
    try {
      await apiPost(`/api/corruption/replies/${id}/decide`, { publish })
      refresh()
    } catch {
      setError('That decision could not be saved.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      <section className="space-y-3">
        <div>
          <h2 className="font-semibold text-ink">Open grievances ({grievances.length})</h2>
          <p className="text-sm text-slate-600">
            Upholding one removes the report from the public feed. Your note goes to the
            complainant <em>and</em> to the anonymous uploader through their tracking code, so
            write it for both and name no third party.
          </p>
        </div>

        {grievances.length === 0 ? (
          <EmptyState title="No open grievances." />
        ) : (
          <ul className="space-y-3">
            {grievances.map((g) => (
              <li key={g.id} className="card space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-mono text-sm font-semibold text-ink">{g.ticket}</p>
                    <p className="text-sm text-slate-700">
                      {g.report_designation}, {g.report_department}
                    </p>
                  </div>
                  <span
                    className={`pill ${
                      g.overdue
                        ? 'bg-red-50 text-red-900 ring-1 ring-red-300/70'
                        : 'bg-slate-100 text-slate-800 ring-1 ring-slate-300/70'
                    }`}
                  >
                    <span aria-hidden className="pill-dot" />
                    Due {new Date(g.resolution_due_by).toLocaleDateString()}
                  </span>
                </div>

                <p className="text-sm">
                  <span className="font-medium capitalize">{g.ground.replace(/_/g, ' ')}</span> —{' '}
                  {g.body}
                </p>

                <p className="text-xs text-slate-600">
                  {g.complainant_name}
                  {g.complainant_designation && `, ${g.complainant_designation}`} ·{' '}
                  <a href={`mailto:${g.complainant_email}`} className="underline">
                    {g.complainant_email}
                  </a>
                  {!g.acknowledged_at && (
                    <span className="ml-2 font-semibold text-red-800">Not yet acknowledged</span>
                  )}
                </p>

                <div>
                  <label className="field-label" htmlFor={`note-${g.id}`}>
                    Reason for the decision
                  </label>
                  <textarea
                    id={`note-${g.id}`}
                    rows={2}
                    className="field-input"
                    value={notes[g.id] ?? ''}
                    onChange={(e) => setNotes((prev) => ({ ...prev, [g.id]: e.target.value }))}
                  />
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={busy === g.id}
                    onClick={() => decide(g.id, true)}
                  >
                    Uphold and remove
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={busy === g.id}
                    onClick={() => decide(g.id, false)}
                  >
                    Reject, content stays
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="font-semibold text-ink">Replies awaiting verification ({replies.length})</h2>
          <p className="text-sm text-slate-600">
            Write to the address below at the department’s own published contact before
            publishing. Nothing here proves the sender is who they say they are.
          </p>
        </div>

        {replies.length === 0 ? (
          <EmptyState title="No replies waiting." />
        ) : (
          <ul className="space-y-3">
            {replies.map((r) => (
              <li key={r.id} className="card space-y-3">
                <div>
                  <p className="text-sm font-semibold text-ink">
                    {r.author_designation}, {r.author_department}
                  </p>
                  <p className="text-xs text-slate-600">
                    Replying to: {r.report_designation}, {r.report_department}
                  </p>
                </div>

                <p className="text-sm text-slate-800">{r.body}</p>

                <p className="text-xs text-slate-600">
                  Signed {r.author_name} ·{' '}
                  <a href={`mailto:${r.author_contact_email}`} className="underline">
                    {r.author_contact_email}
                  </a>{' '}
                  — neither is published.
                </p>

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={busy === r.id}
                    onClick={() => decideReply(r.id, true)}
                  >
                    Verified — publish
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={busy === r.id}
                    onClick={() => decideReply(r.id, false)}
                  >
                    Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
