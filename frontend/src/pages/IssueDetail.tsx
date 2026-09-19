import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import StatusBadge from '../components/StatusBadge'
import { apiGet, type IssueDetail as IssueDetailType, type ShareableCard } from '../lib/api'
import { useI18n } from '../lib/i18n'

export default function IssueDetail() {
  const { issueId } = useParams()
  const { t } = useI18n()
  const [issue, setIssue] = useState<IssueDetailType | null>(null)
  const [card, setCard] = useState<ShareableCard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!issueId) return
    apiGet<IssueDetailType>(`/api/infra/issues/${issueId}`)
      .then(setIssue)
      .catch(() => setError(t('errorGeneric')))
  }, [issueId, t])

  if (error) {
    return (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
        {error}
      </p>
    )
  }
  if (!issue) return <p className="text-slate-600">…</p>

  return (
    <div className="max-w-2xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-ink">{issue.category_label}</h1>
        <StatusBadge status={issue.status} />
      </div>

      {issue.description && <p className="text-slate-700">{issue.description}</p>}

      {issue.media_id && (
        <figure>
          <img
            src={`/api/media/${issue.media_id}`}
            alt={`Citizen-submitted photo of the reported ${issue.category_label}`}
            className="w-full rounded-md border border-slate-200"
          />
          <figcaption className="mt-1 text-xs text-slate-600">
            Faces blurred and metadata stripped at upload.
          </figcaption>
        </figure>
      )}

      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-slate-600">{t('dueBy')}</dt>
          <dd className="font-medium">{new Date(issue.sla_deadline).toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-slate-600">{t('reportedTimes')}</dt>
          <dd className="font-medium">
            {issue.upvote_count} {t('people')}
          </dd>
        </div>
      </dl>

      {issue.resolution_proof_media_id && (
        <figure>
          <figcaption className="field-label">Resolution proof</figcaption>
          <img
            src={`/api/media/${issue.resolution_proof_media_id}`}
            alt="Officer-uploaded photo showing the completed repair"
            className="w-full rounded-md border border-emerald-300"
          />
        </figure>
      )}

      <section>
        <h2 className="mb-2 font-semibold text-ink">History</h2>
        <ol className="space-y-2">
          {issue.history.map((h, i) => (
            <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
              <StatusBadge status={h.status} />
              <span className="text-slate-600">{new Date(h.created_at).toLocaleString()}</span>
              {h.note && <span className="text-slate-700">— {h.note}</span>}
            </li>
          ))}
        </ol>
      </section>

      {issue.status === 'overdue' && (
        <section className="card">
          <h2 className="font-semibold text-ink">{t('shareCard')}</h2>
          <p className="mt-1 text-sm text-slate-600">{t('shareHelp')}</p>
          {card ? (
            <div className="mt-3 space-y-2">
              <p className="rounded bg-slate-100 p-3 text-sm">{card.share_text}</p>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  navigator.clipboard.writeText(card.share_text)
                  setCopied(true)
                }}
              >
                {copied ? t('copied') : t('copy')}
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="btn-primary mt-3"
              onClick={() =>
                apiGet<ShareableCard>(`/api/infra/issues/${issue.id}/share-card`)
                  .then(setCard)
                  .catch(() => setError(t('errorGeneric')))
              }
            >
              {t('shareCard')}
            </button>
          )}
        </section>
      )}
    </div>
  )
}
