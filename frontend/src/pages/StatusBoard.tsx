import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet'

import StatusBadge from '../components/StatusBadge'
import { DEMO_CITY_CENTER, statusMarker } from '../components/mapIcons'
import { apiGet, type Issue, type IssueStatus } from '../lib/api'
import { useI18n } from '../lib/i18n'

const STATUSES: IssueStatus[] = ['reported', 'acknowledged', 'in_progress', 'resolved', 'overdue']

export default function StatusBoard() {
  const { t } = useI18n()
  const [issues, setIssues] = useState<Issue[]>([])
  const [filter, setFilter] = useState<IssueStatus | 'all'>('all')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiGet<Issue[]>('/api/infra/issues')
      .then(setIssues)
      .catch(() => setError(t('errorGeneric')))
  }, [t])

  const visible = useMemo(
    () => (filter === 'all' ? issues : issues.filter((i) => i.status === filter)),
    [issues, filter],
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold text-ink">{t('boardTitle')}</h1>
        <p className="text-sm text-slate-600">
          {visible.length} {t('reportsCount')}
        </p>
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
        <button
          type="button"
          onClick={() => setFilter('all')}
          aria-pressed={filter === 'all'}
          className={filter === 'all' ? 'btn-primary' : 'btn-secondary'}
        >
          {t('filterAll')}
        </button>
        {STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setFilter(s)}
            aria-pressed={filter === s}
            className={filter === s ? 'btn-primary' : 'btn-secondary'}
          >
            <StatusBadge status={s} />
          </button>
        ))}
      </div>

      <div className="h-80 overflow-hidden rounded-md border border-slate-300">
        <MapContainer center={DEMO_CITY_CENTER} zoom={12} scrollWheelZoom={false}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {visible.map((issue) => (
            <Marker key={issue.id} position={[issue.lat, issue.lng]} icon={statusMarker(issue.status)}>
              <Popup>
                <strong>{issue.category_label}</strong>
                <br />
                <Link to={`/issues/${issue.id}`}>Open</Link>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      {visible.length === 0 ? (
        <p className="text-slate-600">{t('noIssues')}</p>
      ) : (
        <ul className="space-y-3">
          {visible.map((issue) => (
            <li key={issue.id} className="card">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <Link
                    to={`/issues/${issue.id}`}
                    className="font-medium text-civic-700 underline underline-offset-2"
                  >
                    {issue.category_label}
                  </Link>
                  {issue.description && (
                    <p className="mt-1 text-sm text-slate-700">{issue.description}</p>
                  )}
                  <p className="mt-1 text-xs text-slate-600">
                    {t('dueBy')} {new Date(issue.sla_deadline).toLocaleString()}
                    {issue.upvote_count > 1 && (
                      <>
                        {' · '}
                        {t('reportedTimes')} {issue.upvote_count} {t('people')}
                      </>
                    )}
                  </p>
                </div>
                <StatusBadge status={issue.status} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
