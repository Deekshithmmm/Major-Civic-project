import { useCallback, useEffect, useState } from 'react'

import ReportMedia from '../ReportMedia'
import StatusBadge from '../StatusBadge'
import { apiGet, apiPost, apiUpload, compressImage, type Issue } from '../../lib/api'
import { useI18n } from '../../lib/i18n'

export default function InfraQueue() {
  const { t } = useI18n()
  const [queue, setQueue] = useState<Issue[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const refresh = useCallback(() => {
    apiGet<Issue[]>('/api/infra/officer/queue')
      .then(setQueue)
      .catch(() => setError(t('errorGeneric')))
  }, [t])

  useEffect(refresh, [refresh])

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
    <div className="space-y-4">
      <h2 className="font-semibold text-ink">
        {t('queueTitle')} ({queue.length})
      </h2>

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
                <ReportMedia
                  mediaId={issue.media_id}
                  kind={issue.media_kind}
                  label={`Submitted ${issue.media_kind === 'video' ? 'video' : 'photo'} for the reported ${issue.category_label}`}
                  className="max-h-48"
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

                <label htmlFor={`proof-${issue.id}`} className="btn-primary cursor-pointer" title={t('proofRequired')}>
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
