import { useState } from 'react'
import { Link } from 'react-router-dom'

import LocationPicker from '../components/LocationPicker'
import TrackingCode from '../components/TrackingCode'
import { ApiError, apiUpload } from '../lib/api'
import { encodeGeohash } from '../lib/geohash'
import { useI18n } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

type Category =
  | 'assault_in_progress'
  | 'homicide_or_body_discovered'
  | 'sexual_offence_adult'
  | 'minor_involved'
  | 'narcotics'
  | 'human_trafficking'

const CATEGORIES: { value: Category; label: string }[] = [
  { value: 'assault_in_progress', label: 'Assault or violence' },
  { value: 'homicide_or_body_discovered', label: 'A death, or a body discovered' },
  { value: 'sexual_offence_adult', label: 'Sexual offence against an adult' },
  { value: 'minor_involved', label: 'Anything involving a child under 18' },
  { value: 'narcotics', label: 'Narcotics sale or manufacture' },
  { value: 'human_trafficking', label: 'Human trafficking' },
]

type SubmitResult = {
  tracking_token: string
  routed_to: string
  station_name: string | null
  evidence_sealed: boolean
  evidence_sha256: string | null
  is_restricted: boolean
  support_resources: { label: string; number: string }[]
}

/**
 * Triage first, camera never first (spec 2.5). A reporting app that opens into a camera teaches
 * bystanders to film an assault instead of calling for help, so Tier A leads with a one-tap 112
 * call and only offers evidence capture afterwards.
 */
export default function EmergencyTriage() {
  const { t } = useI18n()
  usePageTitle('Emergency')
  const [tier, setTier] = useState<'none' | 'a' | 'b'>('none')
  const [category, setCategory] = useState<Category>('assault_in_progress')
  const [point, setPoint] = useState<{ lat: number; lng: number } | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [result, setResult] = useState<SubmitResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isHardStop = category === 'minor_involved'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!point || isHardStop) return
    setError(null)
    setProgress(0)
    try {
      const form = new FormData()
      form.append('category', category)
      form.append('lat', String(point.lat))
      form.append('lng', String(point.lng))
      form.append('geohash', encodeGeohash(point.lat, point.lng))
      if (file) form.append('file', file)
      setResult(await apiUpload<SubmitResult>('/api/emergency/reports', form, setProgress, 5 * 60_000))
    } catch (err) {
      if (err instanceof ApiError && err.kind === 'timeout') setError(t('errorTimeout'))
      else if (err instanceof ApiError && err.kind === 'network') setError(t('errorNetwork'))
      else if (err instanceof ApiError) setError(err.message)
      else setError(t('errorGeneric'))
    } finally {
      setProgress(null)
    }
  }

  if (result) {
    return (
      <div className="card max-w-xl space-y-4" role="status">
        <h1 className="text-xl font-semibold text-ink">{t('emgSubmitted')}</h1>
        <p className="text-sm text-slate-700">
          {t('emgRoutedTo')}: <span className="font-medium">{result.routed_to}</span>
          {result.station_name && <> · {result.station_name}</>}
        </p>
        <p className="text-sm text-slate-700">{t('emgNeverPublic')}</p>

        {result.evidence_sealed && (
          <p className="rounded-md bg-slate-100 p-3 text-xs">
            Evidence sealed. SHA-256:{' '}
            <code className="break-all font-mono">{result.evidence_sha256}</code>
          </p>
        )}

        <TrackingCode token={result.tracking_token} label={t('trackingToken')} />

        <div className="rounded-md bg-civic-50 p-3">
          <h2 className="font-semibold text-ink">{t('emgSupportTitle')}</h2>
          <ul className="mt-1 space-y-1 text-sm">
            {result.support_resources.map((r) => (
              <li key={r.number}>
                {r.label}: <span className="font-semibold">{r.number}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    )
  }

  if (tier === 'none') {
    return (
      <div className="max-w-xl space-y-4">
        <h1 className="text-xl font-semibold text-ink">{t('emgTitle')}</h1>

        <button
          type="button"
          onClick={() => setTier('a')}
          className="w-full rounded-lg border border-red-500/40 bg-red-50 p-4 text-left hover:shadow-sm"
        >
          <span className="block font-semibold text-red-900">{t('emgTierA')}</span>
          <span className="mt-1 block text-sm text-slate-700">{t('emgTierABody')}</span>
        </button>

        <button
          type="button"
          onClick={() => setTier('b')}
          className="w-full rounded-lg border border-slate-300 bg-white p-4 text-left hover:shadow-sm"
        >
          <span className="block font-semibold text-ink">{t('emgTierB')}</span>
          <span className="mt-1 block text-sm text-slate-700">{t('emgTierBBody')}</span>
        </button>

        <p className="text-sm text-slate-600">
          <Link to="/transparency" className="text-civic-700 underline underline-offset-2">
            {t('navTransparency')}
          </Link>{' '}
          — how each station responds to the reports it receives.
        </p>
      </div>
    )
  }

  if (tier === 'a') {
    return (
      <div className="max-w-xl space-y-4">
        <h1 className="text-xl font-semibold text-ink">{t('emgTierA')}</h1>

        <a
          href="tel:112"
          className="block rounded-lg bg-red-600 px-4 py-6 text-center text-2xl font-bold text-white hover:bg-red-700"
        >
          {t('emgCall112')}
        </a>
        <p className="text-sm text-slate-700">{t('emgCallHelp')}</p>

        <button type="button" className="btn-secondary" onClick={() => setTier('b')}>
          {t('emgAfterCall')}
        </button>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="max-w-xl space-y-5">
      <h1 className="text-xl font-semibold text-ink">{t('emgTierB')}</h1>

      <div>
        <label htmlFor="emg-cat" className="field-label">
          {t('emgCategory')}
        </label>
        <select
          id="emg-cat"
          className="field-input"
          value={category}
          onChange={(e) => setCategory(e.target.value as Category)}
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      {isHardStop ? (
        /* Refused in the interface as well as on the server: no upload field is even offered. */
        <div role="alert" className="rounded-lg border border-red-500/40 bg-red-50 p-4">
          <h2 className="font-semibold text-red-900">{t('emgMinorStop')}</h2>
          <p className="mt-1 text-sm text-slate-800">{t('emgMinorStopBody')}</p>
          <ul className="mt-3 space-y-1 text-sm font-medium">
            <li>
              <a className="underline" href="tel:1098">
                Childline: 1098
              </a>
            </li>
            <li>
              <a className="underline" href="tel:112">
                Emergency: 112
              </a>
            </li>
            <li>
              <a className="underline" href="https://cybercrime.gov.in" target="_blank" rel="noreferrer">
                CCPWC cybercrime portal
              </a>
            </li>
          </ul>
        </div>
      ) : (
        <>
          <div>
            <label htmlFor="emg-file" className="field-label">
              {t('emgEvidenceOptional')}
            </label>
            <input
              id="emg-file"
              type="file"
              accept="image/jpeg,image/png,image/webp,video/mp4,video/webm"
              className="field-input"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <p className="mt-1 text-sm text-slate-600">{t('emgNeverPublic')}</p>
          </div>

          <div>
            <span className="field-label">
              {t('location')} <span className="text-red-700">*</span>
            </span>
            <p className="mb-2 text-sm text-slate-600">{t('corrAreaHelp')}</p>
            <LocationPicker value={point} onChange={setPoint} />
          </div>

          {progress !== null && (
            <p className="text-sm text-slate-700" aria-live="polite">
              {progress === 100 ? t('processing') : `${t('submitting')} ${progress}%`}
            </p>
          )}

          {error && (
            <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
              {error}
            </p>
          )}

          <button type="submit" className="btn-primary" disabled={!point || progress !== null}>
            {progress === null ? t('submit') : t('submitting')}
          </button>
        </>
      )}
    </form>
  )
}
