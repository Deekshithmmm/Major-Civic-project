import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MapContainer, Marker, Popup, TileLayer, useMapEvents } from 'react-leaflet'

import { DEMO_CITY_CENTER, pinMarker, statusMarker } from '../components/mapIcons'
import { apiGet, type StationDirectoryEntry } from '../lib/api'
import { useI18n } from '../lib/i18n'

function ClickHandler({ onPick }: { onPick: (p: { lat: number; lng: number }) => void }) {
  useMapEvents({
    click(e) {
      onPick({ lat: e.latlng.lat, lng: e.latlng.lng })
    },
  })
  return null
}

/**
 * Public station directory. A ward can hold more than one station, so "which station covers
 * this spot" is answered by distance rather than by ward - the same rule the server uses when
 * routing a report.
 */
export default function Stations() {
  const { t } = useI18n()
  const [stations, setStations] = useState<StationDirectoryEntry[]>([])
  const [picked, setPicked] = useState<{ lat: number; lng: number } | null>(null)
  const [nearest, setNearest] = useState<StationDirectoryEntry | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiGet<StationDirectoryEntry[]>('/api/station/directory')
      .then(setStations)
      .catch(() => setError(t('errorGeneric')))
  }, [t])

  useEffect(() => {
    if (!picked) return
    apiGet<StationDirectoryEntry>(`/api/station/nearest?lat=${picked.lat}&lng=${picked.lng}`)
      .then(setNearest)
      .catch(() => setNearest(null))
  }, [picked])

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ink">{t('stationsTitle')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-700">{t('stationsIntro')}</p>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      <div className="h-80 overflow-hidden rounded-md border border-slate-300">
        <MapContainer center={DEMO_CITY_CENTER} zoom={12} scrollWheelZoom={false}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickHandler onPick={setPicked} />
          {picked && <Marker position={[picked.lat, picked.lng]} icon={pinMarker} />}
          {stations
            .filter((s) => s.lat !== null && s.lng !== null)
            .map((s) => (
              <Marker
                key={s.id}
                position={[s.lat as number, s.lng as number]}
                icon={statusMarker(s.id === nearest?.id ? 'resolved' : 'acknowledged')}
              >
                <Popup>
                  <strong>{s.name}</strong>
                  <br />
                  {s.address}
                  <br />
                  {s.contact_phone}
                </Popup>
              </Marker>
            ))}
        </MapContainer>
      </div>

      <p className="text-sm text-slate-600">{t('stationsPickHelp')}</p>

      {nearest && (
        <div className="card" role="status">
          <p className="text-sm text-slate-600">{t('stationsNearest')}</p>
          <p className="font-semibold text-ink">{nearest.name}</p>
          <p className="text-sm text-slate-700">
            {nearest.address} · {nearest.distance_km} km
          </p>
          {nearest.contact_phone && (
            <a href={`tel:${nearest.contact_phone}`} className="mt-1 block text-sm text-civic-700 underline">
              {nearest.contact_phone}
            </a>
          )}
          <Link
            to={`/stations/${nearest.id}`}
            className="mt-2 inline-block text-sm font-medium text-civic-700 underline underline-offset-2"
          >
            {t('stationViewAll')} →
          </Link>
        </div>
      )}

      <ul className="grid gap-3 sm:grid-cols-2">
        {stations.map((s) => (
          <li key={s.id}>
            <Link
              to={`/stations/${s.id}`}
              className="flex h-full flex-col rounded-lg border border-slate-200 bg-white p-4 hover:border-civic-600/40 hover:shadow-sm"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-semibold text-ink">{s.name}</span>
                <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold">{s.code}</span>
              </div>

              <dl className="mt-2 space-y-1 text-sm">
                <div className="flex gap-2">
                  <dt className="w-20 shrink-0 text-slate-600">{t('stationAddress')}</dt>
                  <dd className="text-slate-800">{s.address ?? '—'}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-20 shrink-0 text-slate-600">{t('stationWard')}</dt>
                  <dd className="text-slate-800">{s.ward_name ?? '—'}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-20 shrink-0 text-slate-600">{t('stationSho')}</dt>
                  <dd className="text-slate-800">{s.sho_name ?? '—'}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-20 shrink-0 text-slate-600">{t('stationPhone')}</dt>
                  <dd className="text-slate-800">{s.contact_phone ?? '—'}</dd>
                </div>
              </dl>

              <span className="mt-3 text-sm font-medium text-civic-700 underline underline-offset-2">
                {t('stationViewAll')} →
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
