import { useCallback, useEffect, useState } from 'react'

import { apiGet, apiPost } from '../../lib/api'

type StationReport = {
  id: string
  category: string
  geohash: string
  is_restricted: boolean
  has_evidence: boolean
  acknowledged_at: string | null
  fir_number: string | null
  fir_registered_at: string | null
  closed_at: string | null
  closed_without_fir_reason: string | null
  created_at: string
}

type EvidenceAccess = {
  url: string
  expires_seconds: number
  original_sha256: string | null
  chain_of_custody_entries: number
}

type ChainEntry = {
  action: string
  detail: string | null
  officer_user_id: string | null
  case_or_fir_number: string | null
  accessed_at: string
}

/**
 * Investigating-officer view. Evidence is never rendered in the list: it is opened one report at
 * a time, only against a case or FIR number, and every open appends to the chain of custody.
 */
export default function EmergencyPanel() {
  const [reports, setReports] = useState<StationReport[]>([])
  const [caseNumbers, setCaseNumbers] = useState<Record<string, string>>({})
  const [opened, setOpened] = useState<Record<string, EvidenceAccess>>({})
  const [chain, setChain] = useState<Record<string, ChainEntry[]>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const refresh = useCallback(() => {
    apiGet<StationReport[]>('/api/emergency/officer/queue')
      .then(setReports)
      .catch(() => setError('Could not load the queue.'))
  }, [])

  useEffect(refresh, [refresh])

  async function act(id: string, path: string, body?: unknown) {
    setBusy(id)
    setError(null)
    try {
      await apiPost(path, body)
      refresh()
    } catch {
      setError('That action could not be completed.')
    } finally {
      setBusy(null)
    }
  }

  async function openEvidence(id: string) {
    const caseNumber = (caseNumbers[id] ?? '').trim()
    if (!caseNumber) {
      setError('Enter the case or FIR number before opening evidence.')
      return
    }
    setBusy(id)
    setError(null)
    try {
      const access = await apiPost<EvidenceAccess>(`/api/emergency/officer/reports/${id}/evidence`, {
        case_or_fir_number: caseNumber,
      })
      setOpened((prev) => ({ ...prev, [id]: access }))
      setChain((prev) => ({
        ...prev,
        [id]: [],
      }))
      const entries = await apiGet<ChainEntry[]>(`/api/emergency/officer/reports/${id}/chain-of-custody`)
      setChain((prev) => ({ ...prev, [id]: entries }))
    } catch {
      setError('Evidence could not be opened.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-semibold text-ink">Reports ({reports.length})</h2>
        <p className="text-sm text-slate-600">
          Opening evidence requires a case or FIR number and is recorded permanently against your
          officer ID. Restricted reports never appear on any public surface.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      <ul className="space-y-3">
        {reports.map((r) => (
          <li key={r.id} className="card space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-medium">{r.category.replace(/_/g, ' ')}</p>
                <p className="text-xs text-slate-600">
                  Area {r.geohash} · reported {new Date(r.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex flex-wrap gap-1">
                {r.is_restricted && (
                  <span className="rounded-full bg-purple-200 px-2.5 py-0.5 text-xs font-semibold text-purple-900">
                    Restricted
                  </span>
                )}
                <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-semibold">
                  {r.closed_at ? 'Closed' : r.fir_number ? `FIR ${r.fir_number}` : r.acknowledged_at ? 'Acknowledged' : 'Not acknowledged'}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="btn-secondary"
                disabled={busy === r.id || r.acknowledged_at !== null}
                onClick={() => act(r.id, `/api/emergency/officer/reports/${r.id}/acknowledge`)}
              >
                Acknowledge
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={busy === r.id || r.fir_number !== null}
                onClick={() => {
                  const fir = caseNumbers[r.id]?.trim()
                  if (!fir) {
                    setError('Enter the FIR number in the field first.')
                    return
                  }
                  act(r.id, `/api/emergency/officer/reports/${r.id}/fir`, { fir_number: fir })
                }}
              >
                Register FIR
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={busy === r.id || r.closed_at !== null}
                onClick={() => {
                  const reason = caseNumbers[r.id]?.trim()
                  if (!reason) {
                    setError('Type the closure reason in the field first — closure without a reason is not accepted.')
                    return
                  }
                  act(r.id, `/api/emergency/officer/reports/${r.id}/close`, { reason })
                }}
              >
                Close without FIR
              </button>
            </div>

            <div>
              <label htmlFor={`case-${r.id}`} className="field-label">
                Case / FIR number {r.has_evidence && <span className="text-red-700">*</span>}
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  id={`case-${r.id}`}
                  className="field-input max-w-xs"
                  placeholder="FIR/2026/123"
                  value={caseNumbers[r.id] ?? ''}
                  onChange={(e) => setCaseNumbers((prev) => ({ ...prev, [r.id]: e.target.value }))}
                />
                {r.has_evidence ? (
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={busy === r.id}
                    onClick={() => openEvidence(r.id)}
                  >
                    Open sealed evidence
                  </button>
                ) : (
                  <span className="text-sm text-slate-600">No evidence file held</span>
                )}
              </div>
            </div>

            {opened[r.id] && (
              <div className="rounded-md bg-slate-100 p-3 text-sm">
                <p>
                  <a
                    href={opened[r.id].url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-civic-700 underline underline-offset-2"
                  >
                    Open evidence
                  </a>{' '}
                  — link expires in {opened[r.id].expires_seconds}s.
                </p>
                <p className="mt-1 break-all text-xs">
                  Sealed SHA-256: <code className="font-mono">{opened[r.id].original_sha256}</code>
                </p>
                {chain[r.id]?.length > 0 && (
                  <ol className="mt-2 space-y-1 text-xs text-slate-700">
                    {chain[r.id].map((e, i) => (
                      <li key={i}>
                        <span className="font-semibold">{e.action}</span>
                        {e.case_or_fir_number && <> · case {e.case_or_fir_number}</>} ·{' '}
                        {new Date(e.accessed_at).toLocaleString()}
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>

      {reports.length === 0 && <p className="text-slate-600">Nothing in the queue.</p>}
    </div>
  )
}
