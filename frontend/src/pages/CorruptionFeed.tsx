import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import AllegationBadge from '../components/AllegationBadge'
import { EmptyState, ErrorNote, Loading } from '../components/Feedback'
import ReportMedia from '../components/ReportMedia'
import { apiGet, type FeedItem } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

/**
 * The vertical feed from spec 2.3, with the four things that make it survivable: nothing appears
 * until a moderator approves it, every item carries a status badge, no individual is ever named
 * — department and designation only — and the office concerned can answer underneath it.
 */
export default function CorruptionFeed() {
  const { t } = useI18n()
  usePageTitle('Corruption reports')
  const [items, setItems] = useState<FeedItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiGet<FeedItem[]>('/api/corruption/feed')
      .then(setItems)
      .catch(() => setError(t('errorGeneric')))
      .finally(() => setLoading(false))
  }, [t])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-ink">{t('corrFeedTitle')}</h1>
          <p className="mt-1 text-sm text-slate-600">{t('corrFeedDisclaimer')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/corruption/grievance" className="btn-secondary">
            {t('grievanceTitle')}
          </Link>
          <Link to="/corruption/report" className="btn-primary">
            {t('corrReportTitle')}
          </Link>
        </div>
      </div>

      {error && <ErrorNote message={error} />}

      {loading ? (
        <Loading />
      ) : items.length === 0 ? (
        <EmptyState title={t('corrFeedEmpty')} />
      ) : (
        <ul className="max-h-[75vh] snap-y snap-mandatory space-y-4 overflow-y-auto">
          {items.map((item) => (
            <li key={item.id} className="card snap-start space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-ink">{item.accused_department}</p>
                  <p className="text-sm text-slate-700">{item.accused_designation}</p>
                </div>
                <AllegationBadge badge={item.public_status_badge} />
              </div>

              <ReportMedia
                mediaId={item.media_id}
                kind={item.media_kind}
                label={`Submitted evidence concerning ${item.accused_designation}, ${item.accused_department}`}
                className="max-h-[50vh] w-full"
              />

              {item.description && <p className="text-sm text-slate-700">{item.description}</p>}

              {item.replies.map((reply) => (
                <blockquote
                  key={reply.id}
                  className="rounded-lg border-l-4 border-civic-300 bg-civic-50/60 p-3"
                >
                  <p className="text-xs font-semibold uppercase tracking-wide text-civic-800">
                    {t('replyPublishedLabel')}
                  </p>
                  <p className="text-xs text-slate-700">
                    {reply.author_designation}, {reply.author_department}
                  </p>
                  <p className="mt-1.5 text-sm text-slate-800">{reply.body}</p>
                </blockquote>
              ))}

              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-slate-600">
                  Area {item.geohash} · {new Date(item.created_at).toLocaleDateString()}
                </p>
                <Link
                  to={`/corruption/respond/${item.id}`}
                  className="text-xs font-medium text-civic-700 underline underline-offset-2"
                >
                  {t('grievanceRespondLink')} →
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
