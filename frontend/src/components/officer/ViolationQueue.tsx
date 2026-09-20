import { useCallback, useEffect, useState } from 'react'

import ReportMedia from '../ReportMedia'
import { apiGet, apiPost, type Challan, type ViolationCase, type ViolationClass } from '../../lib/api'

/**
 * The officer review queue from spec 2.2. Nothing here issues a fine by itself: a challan exists
 * only after an officer confirms a case, and the officer who confirmed it is refused the appeal.
 */
export default function ViolationQueue() {
  const [cases, setCases] = useState<ViolationCase[]>([])
  const [classes, setClasses] = useState<ViolationClass[]>([])
  const [disputes, setDisputes] = useState<Challan[]>([])
  const [issued, setIssued] = useState<Challan | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const refresh = useCallback(() => {
    apiGet<ViolationCase[]>('/api/violations/officer/queue').then(setCases).catch(() => setError('Could not load the queue.'))
    apiGet<Challan[]>('/api/violations/officer/disputes').then(setDisputes).catch(() => undefined)
  }, [])

  useEffect(() => {
    apiGet<ViolationClass[]>('/api/violations/classes').then(setClasses).catch(() => undefined)
    refresh()
  }, [refresh])

  async function act(id: string, path: string, body?: unknown) {
    setBusy(id)
    setError(null)
    try {
      const res = await apiPost<Challan>(path, body)
      if (path.endsWith('/confirm')) setIssued(res)
      refresh()
    } catch {
      setError('That action could not be completed.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      {issued && (
        <div role="status" className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-900">
          Challan issued: <strong>Rs. {issued.amount_rupees}</strong>
          {issued.statutory_section && <> under {issued.statutory_section}</>}, due{' '}
          {new Date(issued.due_date).toLocaleDateString()}. The citizen can dispute it, and a
          different officer must rule on that appeal.
        </div>
      )}

      <section>
        <h2 className="mb-2 font-semibold text-ink">Pending review ({cases.length})</h2>
        {cases.length === 0 ? (
          <p className="text-slate-600">No cases waiting.</p>
        ) : (
          <ul className="space-y-3">
            {cases.map((c) => (
              <li key={c.id} className="card space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{c.violation_class_label}</p>
                    <p className="text-xs text-slate-600">
                      {c.source === 'citizen_upload' ? 'Citizen upload' : `Camera ${c.source}`}
                      {c.confidence_score !== null && <> · confidence {Math.round(c.confidence_score * 100)}%</>}
                      {' · '}
                      {c.lat.toFixed(4)}, {c.lng.toFixed(4)}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-semibold">
                    {c.identity_path === 'anpr' ? c.resolved_plate_number ?? 'Plate unresolved' : 'Unidentified case'}
                  </span>
                </div>

                <ReportMedia
                  mediaId={c.media_id}
                  kind={c.media_kind}
                  label={`Evidence for the reported ${c.violation_class_label}`}
                  className="max-h-56"
                />

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={busy === c.id}
                    onClick={() => act(c.id, `/api/violations/officer/cases/${c.id}/confirm`)}
                  >
                    Confirm and issue challan
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={busy === c.id}
                    onClick={() => act(c.id, `/api/violations/officer/cases/${c.id}/dismiss`)}
                  >
                    Dismiss
                  </button>
                  <label htmlFor={`reclass-${c.id}`} className="sr-only">
                    Reclassify this case
                  </label>
                  <select
                    id={`reclass-${c.id}`}
                    className="rounded-md border border-slate-300 px-2 py-2 text-sm"
                    defaultValue=""
                    disabled={busy === c.id}
                    onChange={(e) => {
                      if (e.target.value) {
                        act(c.id, `/api/violations/officer/cases/${c.id}/reclassify`, {
                          new_violation_class_slug: e.target.value,
                        })
                      }
                    }}
                  >
                    <option value="">Reclassify as…</option>
                    {classes
                      .filter((k) => k.slug !== c.violation_class_slug)
                      .map((k) => (
                        <option key={k.slug} value={k.slug}>
                          {k.label}
                        </option>
                      ))}
                  </select>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-2 font-semibold text-ink">Disputed challans ({disputes.length})</h2>
        {disputes.length === 0 ? (
          <p className="text-slate-600">No disputes.</p>
        ) : (
          <ul className="space-y-3">
            {disputes.map((d) => (
              <li key={d.id} className="card flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium">Rs. {d.amount_rupees}</p>
                  <p className="text-xs text-slate-600">{d.statutory_section}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={busy === d.id}
                    onClick={() => act(d.id, `/api/violations/officer/disputes/${d.id}/uphold`)}
                  >
                    Uphold
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={busy === d.id}
                    onClick={() => act(d.id, `/api/violations/officer/disputes/${d.id}/overturn`)}
                  >
                    Overturn
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
