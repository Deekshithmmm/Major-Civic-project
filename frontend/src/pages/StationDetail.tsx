import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { MapContainer, Marker, TileLayer } from 'react-leaflet'

import { ErrorNote, Loading } from '../components/Feedback'
import { statusMarker } from '../components/mapIcons'
import { apiGet, type StationDetail as StationDetailType } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: 'bad' | 'good' }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <span
        className={`block text-2xl font-semibold ${
          tone === 'bad' ? 'text-red-800' : tone === 'good' ? 'text-emerald-800' : 'text-ink'
        }`}
      >
        {value}
      </span>
      <span className="mt-0.5 block text-xs text-slate-600">{label}</span>
    </div>
  )
}

export default function StationDetail() {
  const { stationId } = useParams()
  const { t } = useI18n()
  const [station, setStation] = useState<StationDetailType | null>(null)
  const [error, setError] = useState<string | null>(null)
  usePageTitle(station?.name ?? 'Police station')

  useEffect(() => {
    if (!stationId) return
    apiGet<StationDetailType>(`/api/station/${stationId}`)
      .then(setStation)
      .catch(() => setError(t('errorGeneric')))
  }, [stationId, t])

  if (error) return <ErrorNote message={error} />
  if (!station) return <Loading rows={4} />

  return (
    <div className="space-y-6">
      <div>
        <Link to="/stations" className="text-sm text-civic-700 underline underline-offset-2">
          ← {t('stationsTitle')}
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold text-ink">{station.name}</h1>
            <p className="text-sm text-slate-700">{station.address}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-semibold">{station.code}</span>
            {station.flagged_red && (
              <span className="rounded-full bg-red-200 px-2.5 py-0.5 text-xs font-semibold text-red-900">
                {t('stationFlagged')}
              </span>
            )}
          </div>
        </div>
      </div>

      <dl className="grid gap-3 sm:grid-cols-2">
        <div className="card">
          <dt className="text-xs text-slate-600">{t('stationSho')}</dt>
          <dd className="font-medium text-ink">{station.sho_name ?? '—'}</dd>
        </div>
        <div className="card">
          <dt className="text-xs text-slate-600">{t('stationWard')}</dt>
          <dd className="font-medium text-ink">{station.ward_name ?? '—'}</dd>
        </div>
        <div className="card">
          <dt className="text-xs text-slate-600">{t('stationPhone')}</dt>
          <dd className="font-medium">
            {station.contact_phone ? (
              <a href={`tel:${station.contact_phone}`} className="text-civic-700 underline underline-offset-2">
                {station.contact_phone}
              </a>
            ) : (
              '—'
            )}
          </dd>
        </div>
        <div className="card">
          <dt className="text-xs text-slate-600">{t('stationEmergency')}</dt>
          <dd className="font-medium">
            <a href="tel:112" className="text-red-700 underline underline-offset-2">
              112
            </a>
          </dd>
        </div>
      </dl>

      {station.lat !== null && station.lng !== null && (
        <div className="h-64 overflow-hidden rounded-md border border-slate-300">
          <MapContainer center={[station.lat, station.lng]} zoom={15} scrollWheelZoom={false}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <Marker position={[station.lat, station.lng]} icon={statusMarker('acknowledged')} />
          </MapContainer>
        </div>
      )}

      <section>
        <h2 className="font-semibold text-ink">{t('stationResponseTitle')}</h2>
        <p className="mb-3 text-sm text-slate-600">{t('stationResponseIntro')}</p>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label={t('stationReports30')} value={station.reports_30d} />
          <Stat label={t('stationReports90')} value={station.reports_90d} />
          <Stat
            label={t('stationUnack')}
            value={station.unacknowledged_past_sla}
            tone={station.unacknowledged_past_sla > 0 ? 'bad' : undefined}
          />
          <Stat label={t('stationFirs')} value={station.firs_registered} />
          <Stat
            label={t('stationConversion')}
            value={station.fir_conversion_rate === null ? '—' : `${Math.round(station.fir_conversion_rate * 100)}%`}
          />
          <Stat
            label={t('stationMedianAck')}
            value={station.median_ack_hours === null ? '—' : `${station.median_ack_hours}h`}
          />
          <Stat
            label={t('stationPastFirSla')}
            value={station.open_past_fir_sla}
            tone={station.open_past_fir_sla > 0 ? 'bad' : undefined}
          />
          <Stat label={t('stationClosedNoFir')} value={station.closed_without_fir} />
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <h2 className="font-semibold text-ink">{t('stationNotShownTitle')}</h2>
        <p className="mt-1 text-sm text-slate-700">{t('stationNotShownBody')}</p>
        <Link
          to="/transparency"
          className="mt-2 inline-block text-sm font-medium text-civic-700 underline underline-offset-2"
        >
          {t('homeSeeLedger')} →
        </Link>
      </section>
    </div>
  )
}
