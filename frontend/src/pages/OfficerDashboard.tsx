import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import StatusBadge from '../components/StatusBadge'
import {
  apiGet,
  apiPost,
  apiUpload,
  clearToken,
  compressImage,
  getToken,
  type CurrentUser,
  type Issue,
} from '../lib/api'
import { useI18n } from '../lib/i18n'

export default function OfficerDashboard() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [queue, setQueue] = useState<Issue[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const refresh = useCallback(() => {
    apiGet<Issue[]>('/api/infra/officer/queue')
      .then(setQueue)
      .catch(() => setError(t('errorGeneric')))
  }, [t])

  useEffect(() => {
    if (!getToken()) {
      navigate('/officer')
      return
    }
    apiGet<CurrentUser>('/api/auth/me')
      .then(setUser)
      .catch(() => {
        clearToken()
        navigate('/officer')
      })
    refresh()
  }, [navigate, refresh])

  async function act(issueId: string, action: 'acknowledge' | 'start') {
    setBusyId(issueId)
    try {
      await apiPost(`/api/infra/officer/issues/${issueId}/${action}`)
      refresh()
    } catch {
      setError(t('errorGeneric'))
    } finally {
      setBusyId(null)
    }
  }

  async function resolve(issueId: string, file: File) {
    setBusyId(issueId)
    try {
      const form = new FormData()
      form.append('proof_file', await compressImage(file))
      await apiUpload(`/api/infra/officer/issues/${issueId}/resolve`, form)
      refresh()
    } catch {
      setError(t('errorGeneric'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-ink">{t('queueTitle')}</h1>
          {user && (
            <p className="text-sm text-slate-600">
              {user.full_name} · {user.role.replace(/_/g, ' ')}
            </p>
          )}
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => {
            clearToken()
            navigate('/officer')
          }}
        >
          {t('logout')}
        </button>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      {queue.length === 0 ? (
        <p className="text-slate-600">{t('noIssues')}</p>
      ) : (
        <ul className="space-y-3">
          {queue.map((issue) => (
            <li key={issue.id} className="card space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{issue.category_label}</p>
                  {issue.description && <p className="text-sm text-slate-700">{issue.description}</p>}
                  <p className="mt-1 text-xs text-slate-600">
                    {t('dueBy')} {new Date(issue.sla_deadline).toLocaleString()}
                  </p>
                </div>
                <StatusBadge status={issue.status} />
              </div>

              {issue.media_id && (
                <img
                  src={`/api/media/${issue.media_id}`}
                  alt={`Submitted photo for the reported ${issue.category_label}`}
                  className="max-h-48 rounded-md border border-slate-200"
                />
              )}

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={busyId === issue.id || issue.status !== 'reported'}
                  onClick={() => act(issue.id, 'acknowledge')}
                >
                  {t('acknowledge')}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={busyId === issue.id || issue.status === 'in_progress'}
                  onClick={() => act(issue.id, 'start')}
                >
                  {t('startWork')}
                </button>

                <label
                  htmlFor={`proof-${issue.id}`}
                  className="btn-primary cursor-pointer"
                  title={t('proofRequired')}
                >
                  {t('resolveWithProof')}
                </label>
                <input
                  id={`proof-${issue.id}`}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="sr-only"
                  disabled={busyId === issue.id}
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) resolve(issue.id, f)
                  }}
                />
              </div>
              <p className="text-xs text-slate-600">{t('proofRequired')}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
