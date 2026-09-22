import { useCallback, useEffect, useState } from 'react'

import {
  apiGet,
  apiPost,
  type CaseDiaryEntry,
  type DiaryEntry,
  type FirRecord,
  type StationDirectoryEntry,
  type StationReportRow,
  type StationSummary,
} from '../../lib/api'

type Tab = 'reports' | 'firs' | 'diary'

/**
 * The internal station section: the queue, the FIR register and the General Diary.
 *
 * Every procedure here writes a diary line on the server, so the diary tab is the station's own
 * account of what it did and when - which is exactly what the public response ledger measures.
 */
export default function StationPanel() {
  const [station, setStation] = useState<StationSummary | null>(null)
  const [tab, setTab] = useState<Tab>('reports')
  const [reports, setReports] = useState<StationReportRow[]>([])
  const [firs, setFirs] = useState<FirRecord[]>([])
  const [diary, setDiary] = useState<DiaryEntry[]>([])
  const [stations, setStations] = useState<StationDirectoryEntry[]>([])
  const [caseDiary, setCaseDiary] = useState<Record<string, CaseDiaryEntry[]>>({})
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const refresh = useCallback(() => {
    apiGet<StationReportRow[]>('/api/station/reports').then(setReports).catch(() => setError('Could not load the queue.'))
    apiGet<FirRecord[]>('/api/station/firs').then(setFirs).catch(() => undefined)
    apiGet<DiaryEntry[]>('/api/station/diary').then(setDiary).catch(() => undefined)
  }, [])

  useEffect(() => {
    apiGet<StationSummary>('/api/station/me')
      .then(setStation)
      .catch(() => setError('Your account is not posted to a police station.'))
    apiGet<StationDirectoryEntry[]>('/api/station/directory').then(setStations).catch(() => undefined)
    refresh()
  }, [refresh])

  const draft = (key: string) => drafts[key] ?? ''
  const setDraft = (key: string, value: string) => setDrafts((d) => ({ ...d, [key]: value }))

  async function run(key: string, path: string, body?: unknown, success?: string) {
    setBusy(key)
    setError(null)
    setNotice(null)
    try {
      await apiPost(path, body)
      if (success) setNotice(success)
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That action could not be completed.')
    } finally {
      setBusy(null)
    }
  }

  async function loadCaseDiary(firId: string) {
    const entries = await apiGet<CaseDiaryEntry[]>(`/api/station/firs/${firId}/case-diary`)
    setCaseDiary((c) => ({ ...c, [firId]: entries }))
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold text-ink">{station ? `${station.name} (${station.code})` : 'Station'}</h2>
          {station && (
            <p className="text-sm text-slate-600">
              {station.address}
              {station.sho_name && <> · SHO {station.sho_name}</>}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Station sections">
          {(
            [
              ['reports', `Reports (${reports.length})`],
              ['firs', `FIR register (${firs.length})`],
              ['diary', 'General Diary'],
            ] as [Tab, string][]
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={tab === id ? 'btn-primary' : 'btn-secondary'}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-900">
          {notice}
        </p>
      )}

      {tab === 'reports' && (
        <ul className="space-y-3">
          {reports.length === 0 && <p className="text-slate-600">Nothing routed to this station.</p>}
          {reports.map((r) => (
            <li key={r.id} className={`card space-y-3 ${r.overdue_for_fir ? 'border-red-300 bg-red-50' : ''}`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{r.category.replace(/_/g, ' ')}</p>
                  <p className="text-xs text-slate-600">
                    area {r.geohash} · {r.hours_since_report}h old
                    {r.has_evidence && <> · evidence sealed</>}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1">
                  {r.is_restricted && (
                    <span className="rounded-full bg-purple-200 px-2.5 py-0.5 text-xs font-semibold text-purple-900">
                      Restricted
                    </span>
                  )}
                  {r.fir_number ? (
                    <span className="rounded-full bg-emerald-200 px-2.5 py-0.5 text-xs font-semibold text-emerald-900">
                      FIR {r.fir_number}
                    </span>
                  ) : r.closed_at ? (
                    <span className="rounded-full bg-slate-300 px-2.5 py-0.5 text-xs font-semibold">Closed</span>
                  ) : r.overdue_for_fir ? (
                    <span className="rounded-full bg-red-200 px-2.5 py-0.5 text-xs font-semibold text-red-900">
                      No FIR past 7 days
                    </span>
                  ) : r.overdue_for_acknowledgement ? (
                    <span className="rounded-full bg-amber-200 px-2.5 py-0.5 text-xs font-semibold text-amber-900">
                      Unacknowledged past 24h
                    </span>
                  ) : (
                    <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-semibold">
                      {r.acknowledged_at ? 'Acknowledged' : 'New'}
                    </span>
                  )}
                </div>
              </div>

              {!r.fir_number && !r.closed_at && (
                <div className="space-y-2">
                  <div className="flex flex-wrap items-end gap-2">
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={busy === r.id || r.acknowledged_at !== null}
                      onClick={() => run(r.id, `/api/station/reports/${r.id}/acknowledge`, undefined, 'Acknowledged.')}
                    >
                      Acknowledge
                    </button>
                    <div>
                      <label htmlFor={`sec-${r.id}`} className="field-label">
                        Sections invoked
                      </label>
                      <input
                        id={`sec-${r.id}`}
                        className="field-input max-w-xs"
                        placeholder="e.g. BNS 115(2)"
                        value={draft(`sec-${r.id}`)}
                        onChange={(e) => setDraft(`sec-${r.id}`, e.target.value)}
                      />
                    </div>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={busy === r.id || draft(`sec-${r.id}`).trim().length < 2}
                      onClick={() =>
                        run(
                          r.id,
                          `/api/station/reports/${r.id}/fir`,
                          { sections: draft(`sec-${r.id}`).trim(), is_zero_fir: false },
                          'FIR registered — the number is issued by the station in sequence.',
                        )
                      }
                    >
                      Register FIR
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={busy === r.id || draft(`sec-${r.id}`).trim().length < 2}
                      title="Register even though the offence falls outside this station's jurisdiction, then transfer"
                      onClick={() =>
                        run(
                          r.id,
                          `/api/station/reports/${r.id}/fir`,
                          { sections: draft(`sec-${r.id}`).trim(), is_zero_fir: true },
                          'Zero FIR registered. Transfer it from the FIR register.',
                        )
                      }
                    >
                      Register as Zero FIR
                    </button>
                  </div>

                  <div className="flex flex-wrap items-end gap-2">
                    <div>
                      <label htmlFor={`close-${r.id}`} className="field-label">
                        Or close without an FIR — reason is published
                      </label>
                      <input
                        id={`close-${r.id}`}
                        className="field-input max-w-md"
                        placeholder="Reason for closure"
                        value={draft(`close-${r.id}`)}
                        onChange={(e) => setDraft(`close-${r.id}`, e.target.value)}
                      />
                    </div>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={busy === r.id || draft(`close-${r.id}`).trim().length < 3}
                      onClick={() =>
                        run(r.id, `/api/station/reports/${r.id}/close`, { reason: draft(`close-${r.id}`).trim() }, 'Closed.')
                      }
                    >
                      Close
                    </button>
                  </div>
                </div>
              )}

              {r.closed_without_fir_reason && (
                <p className="text-sm text-slate-700">Closed: {r.closed_without_fir_reason}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {tab === 'firs' && (
        <ul className="space-y-3">
          {firs.length === 0 && <p className="text-slate-600">No FIRs registered yet.</p>}
          {firs.map((f) => (
            <li key={f.id} className="card space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-ink">
                    FIR {f.fir_number}
                    {f.is_zero_fir && <span className="ml-2 text-xs font-semibold text-amber-800">ZERO FIR</span>}
                  </p>
                  <p className="text-sm text-slate-700">u/s {f.sections}</p>
                  <p className="text-xs text-slate-600">
                    registered {new Date(f.registered_at).toLocaleDateString()} ·{' '}
                    {f.status === 'under_investigation'
                      ? `${f.days_remaining} days left to conclude`
                      : f.status.replace(/_/g, ' ')}
                    {f.court_name && <> · {f.court_name}</>}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    f.status === 'chargesheet_filed'
                      ? 'bg-emerald-200 text-emerald-900'
                      : f.days_remaining < 0
                        ? 'bg-red-200 text-red-900'
                        : 'bg-slate-200'
                  }`}
                >
                  {f.status.replace(/_/g, ' ')}
                </span>
              </div>

              {f.status === 'under_investigation' && (
                <div className="space-y-2">
                  <div className="flex flex-wrap items-end gap-2">
                    <div className="min-w-0 flex-1">
                      <label htmlFor={`cd-${f.id}`} className="field-label">
                        Case diary entry
                      </label>
                      <input
                        id={`cd-${f.id}`}
                        className="field-input"
                        placeholder="What was done today"
                        value={draft(`cd-${f.id}`)}
                        onChange={(e) => setDraft(`cd-${f.id}`, e.target.value)}
                      />
                    </div>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={busy === f.id || draft(`cd-${f.id}`).trim().length < 3}
                      onClick={async () => {
                        await run(f.id, `/api/station/firs/${f.id}/case-diary`, { detail: draft(`cd-${f.id}`).trim() })
                        setDraft(`cd-${f.id}`, '')
                        loadCaseDiary(f.id)
                      }}
                    >
                      Add
                    </button>
                    <button type="button" className="btn-secondary" onClick={() => loadCaseDiary(f.id)}>
                      View diary
                    </button>
                  </div>

                  <div className="flex flex-wrap items-end gap-2">
                    <div>
                      <label htmlFor={`court-${f.id}`} className="field-label">
                        File chargesheet before
                      </label>
                      <input
                        id={`court-${f.id}`}
                        className="field-input max-w-xs"
                        placeholder="Court"
                        value={draft(`court-${f.id}`)}
                        onChange={(e) => setDraft(`court-${f.id}`, e.target.value)}
                      />
                    </div>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={busy === f.id || draft(`court-${f.id}`).trim().length < 2}
                      onClick={() =>
                        run(
                          f.id,
                          `/api/station/firs/${f.id}/chargesheet`,
                          { court_name: draft(`court-${f.id}`).trim() },
                          'Chargesheet filed. The case record becomes public from this point.',
                        )
                      }
                    >
                      File chargesheet
                    </button>
                  </div>

                  {f.is_zero_fir && !f.transferred_to_station_id && (
                    <div className="flex flex-wrap items-end gap-2">
                      <div>
                        <label htmlFor={`to-${f.id}`} className="field-label">
                          Transfer investigation to
                        </label>
                        <select
                          id={`to-${f.id}`}
                          className="field-input max-w-xs"
                          value={draft(`to-${f.id}`)}
                          onChange={(e) => setDraft(`to-${f.id}`, e.target.value)}
                        >
                          <option value="">Select station…</option>
                          {stations
                            .filter((s) => s.id !== f.station_id)
                            .map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.name}
                              </option>
                            ))}
                        </select>
                      </div>
                      <button
                        type="button"
                        className="btn-secondary"
                        disabled={busy === f.id || !draft(`to-${f.id}`)}
                        onClick={() =>
                          run(
                            f.id,
                            `/api/station/firs/${f.id}/transfer`,
                            { to_station_id: draft(`to-${f.id}`), reason: 'Offence falls within their jurisdiction' },
                            'Transferred. The registration stays with this station.',
                          )
                        }
                      >
                        Transfer
                      </button>
                    </div>
                  )}
                </div>
              )}

              {caseDiary[f.id] && (
                <ol className="space-y-1 rounded-md bg-slate-100 p-3 text-xs text-slate-700">
                  {caseDiary[f.id].length === 0 && <li>No case diary entries yet.</li>}
                  {caseDiary[f.id].map((e) => (
                    <li key={e.id}>
                      {new Date(e.created_at).toLocaleString()} — {e.detail}
                    </li>
                  ))}
                </ol>
              )}
            </li>
          ))}
        </ul>
      )}

      {tab === 'diary' && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-0 flex-1">
              <label htmlFor="gd-note" className="field-label">
                Add a General Diary entry
              </label>
              <input
                id="gd-note"
                className="field-input"
                placeholder="Entry"
                value={draft('gd')}
                onChange={(e) => setDraft('gd', e.target.value)}
              />
            </div>
            <button
              type="button"
              className="btn-primary"
              disabled={busy === 'gd' || draft('gd').trim().length < 3}
              onClick={async () => {
                await run('gd', '/api/station/diary', { detail: draft('gd').trim() })
                setDraft('gd', '')
              }}
            >
              Add entry
            </button>
          </div>
          <p className="text-xs text-slate-600">
            Entries cannot be edited or deleted once written — the database refuses it, the way a
            bound register does.
          </p>

          <ol className="space-y-2">
            {diary.map((e) => (
              <li key={e.id} className="card py-2 text-sm">
                <span className="font-mono text-xs text-slate-600">
                  GD {e.serial_no} of {e.entry_date}
                </span>
                <span className="ml-2 rounded-full bg-slate-200 px-2 py-0.5 text-xs">
                  {e.entry_type.replace(/_/g, ' ')}
                </span>
                <p className="mt-1 text-slate-800">{e.detail}</p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
