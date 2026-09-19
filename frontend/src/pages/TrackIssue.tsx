import { useState } from 'react'

import StatusBadge from '../components/StatusBadge'
import { ApiError, apiGet, type IssueDetail } from '../lib/api'
import { useI18n } from '../lib/i18n'

export default function TrackIssue() {
  const { t } = useI18n()
  const [token, setToken] = useState('')
  const [issue, setIssue] = useState<IssueDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function lookup(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setIssue(null)
    setLoading(true)
    try {
      setIssue(await apiGet<IssueDetail>(`/api/infra/issues/track/${encodeURIComponent(token.trim())}`))
    } catch (err) {
      setError(err instanceof ApiError && err.status === 404 ? t('trackNotFound') : t('errorGeneric'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-xl space-y-5">
      <h1 className="text-xl font-semibold text-ink">{t('trackTitle')}</h1>

      <form onSubmit={lookup} className="flex flex-wrap items-end gap-2">
        <div className="min-w-0 flex-1">
          <label htmlFor="token" className="field-label">
            {t('trackingToken')}
          </label>
          <input
            id="token"
            className="field-input"
            placeholder={t('trackPlaceholder')}
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
          />
        </div>
        <button type="submit" className="btn-primary" disabled={loading || !token.trim()}>
          {t('trackButton')}
        </button>
      </form>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      {issue && (
        <div className="card space-y-3" role="status">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold text-ink">{issue.category_label}</h2>
            <StatusBadge status={issue.status} />
          </div>
          <p className="text-sm text-slate-600">
            {t('dueBy')} {new Date(issue.sla_deadline).toLocaleString()}
          </p>
          <ol className="space-y-2">
            {issue.history.map((h, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
                <StatusBadge status={h.status} />
                <span className="text-slate-600">{new Date(h.created_at).toLocaleString()}</span>
                {h.note && <span className="text-slate-700">— {h.note}</span>}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
