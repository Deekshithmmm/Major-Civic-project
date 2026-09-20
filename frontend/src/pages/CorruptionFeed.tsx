import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import AllegationBadge from '../components/AllegationBadge'
import ReportMedia from '../components/ReportMedia'
import { apiGet, type FeedItem } from '../lib/api'
import { useI18n } from '../lib/i18n'

/**
 * The vertical feed from spec 2.3, with the three things that make it survivable: nothing appears
 * until a moderator approves it, every item carries a status badge, and no individual is ever
 * named — department and designation only.
 */
export default function CorruptionFeed() {
  const { t } = useI18n()
  const [items, setItems] = useState<FeedItem[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiGet<FeedItem[]>('/api/corruption/feed')
      .then(setItems)
      .catch(() => setError(t('errorGeneric')))
  }, [t])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-ink">{t('corrFeedTitle')}</h1>
          <p className="mt-1 text-sm text-slate-600">{t('corrFeedDisclaimer')}</p>
        </div>
        <Link to="/corruption/report" className="btn-primary">
          {t('corrReportTitle')}
        </Link>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      {items.length === 0 ? (
        <p className="text-slate-600">{t('corrFeedEmpty')}</p>
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

              <p className="text-xs text-slate-600">
                Area {item.geohash} · {new Date(item.created_at).toLocaleDateString()}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
