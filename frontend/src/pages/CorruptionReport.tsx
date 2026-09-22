import { useEffect, useState } from 'react'

import LocationPicker from '../components/LocationPicker'
import TrackingCode from '../components/TrackingCode'
import {
  ApiError,
  apiGet,
  apiUpload,
  compressImage,
  type AccusedPartyType,
  type CorruptionReportResult,
  type RoutingRule,
} from '../lib/api'
import { GEOHASH_CELL_DESCRIPTION, encodeGeohash } from '../lib/geohash'
import { useI18n } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

const PARTY_TYPES: { value: AccusedPartyType; label: string }[] = [
  { value: 'municipal_or_dept_staff', label: 'Municipal or departmental staff' },
  { value: 'state_govt_employee', label: 'State government employee' },
  { value: 'central_govt_employee', label: 'Central government employee' },
  { value: 'police_personnel', label: 'Police personnel' },
]

export default function CorruptionReport() {
  const { t } = useI18n()
  usePageTitle('Report corruption')
  const [rules, setRules] = useState<RoutingRule[]>([])
  const [partyType, setPartyType] = useState<AccusedPartyType>('municipal_or_dept_staff')
  const [department, setDepartment] = useState('')
  const [designation, setDesignation] = useState('')
  const [description, setDescription] = useState('')
  const [point, setPoint] = useState<{ lat: number; lng: number } | null>(null)
  const [file, setFile] = useState<File | null>(null)

  const [progress, setProgress] = useState<number | null>(null)
  const [result, setResult] = useState<CorruptionReportResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const processing = progress === 100
  const rule = rules.find((r) => r.accused_party_type === partyType)

  useEffect(() => {
    apiGet<RoutingRule[]>('/api/corruption/routing-rules')
      .then(setRules)
      .catch(() => setError(t('errorGeneric')))
  }, [t])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!file || !point) return
    setError(null)
    setProgress(0)
    try {
      const prepared = await compressImage(file)
      const form = new FormData()
      form.append('accused_department', department)
      form.append('accused_designation', designation)
      form.append('accused_party_type', partyType)
      if (description) form.append('description', description)
      // Only the coarse cell leaves the browser — never the exact point picked.
      form.append('geohash', encodeGeohash(point.lat, point.lng))
      form.append('file', prepared)

      const timeout = prepared.type.startsWith('video/') ? 5 * 60_000 : 2 * 60_000
      setResult(await apiUpload<CorruptionReportResult>('/api/corruption/reports', form, setProgress, timeout))
    } catch (err) {
      if (err instanceof ApiError && err.kind === 'timeout') setError(t('errorTimeout'))
      else if (err instanceof ApiError && err.kind === 'network') setError(t('errorNetwork'))
      else setError(t('errorGeneric'))
    } finally {
      setProgress(null)
    }
  }

  if (result) {
    return (
      <div className="card max-w-xl" role="status">
        <h1 className="text-xl font-semibold text-ink">{t('submitted')}</h1>
        <p className="mt-2 text-sm text-slate-700">{t('corrSubmitted')}</p>
        <div className="mt-4">
          <TrackingCode token={result.tracking_token} label={t('trackingToken')} />
        </div>
        <p className="mt-2 text-sm text-slate-600">{t('trackingHelp')}</p>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="max-w-xl space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ink">{t('corrReportTitle')}</h1>
        <p className="mt-1 text-sm text-slate-600">{t('corrAnonIntro')}</p>
      </div>

      <div>
        <label htmlFor="party" className="field-label">
          {t('corrPartyType')}
        </label>
        <select
          id="party"
          className="field-input"
          value={partyType}
          onChange={(e) => setPartyType(e.target.value as AccusedPartyType)}
        >
          {PARTY_TYPES.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>

        {rule && (
          <div className="mt-2 rounded-md bg-civic-50 p-3 text-sm" aria-live="polite">
            <p>
              <span className="text-slate-700">{t('corrRoutedTo')}:</span>{' '}
              <span className="font-medium text-ink">{rule.primary_route_body}</span>
            </p>
            {partyType === 'police_personnel' && (
              <p className="mt-1 font-medium text-civic-700">{t('corrPoliceNever')}</p>
            )}
          </div>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="dept" className="field-label">
            {t('corrDepartment')} <span className="text-red-700">*</span>
          </label>
          <input
            id="dept"
            required
            className="field-input"
            placeholder="e.g. Municipal Licensing Office"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="desig" className="field-label">
            {t('corrDesignation')} <span className="text-red-700">*</span>
          </label>
          <input
            id="desig"
            required
            className="field-input"
            placeholder="e.g. Licensing Inspector"
            value={designation}
            onChange={(e) => setDesignation(e.target.value)}
          />
        </div>
      </div>

      <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">{t('corrNoNames')}</p>

      <div>
        <label htmlFor="desc" className="field-label">
          {t('description')}
        </label>
        <textarea
          id="desc"
          rows={3}
          className="field-input"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div>
        <label htmlFor="corr-file" className="field-label">
          {t('photo')} <span className="text-red-700">*</span>
        </label>
        <input
          id="corr-file"
          type="file"
          required
          accept="image/jpeg,image/png,image/webp,video/mp4,video/webm"
          className="field-input"
          aria-describedby="corr-file-help"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <p id="corr-file-help" className="mt-1 text-sm text-slate-600">
          {t('photoHelp')}
        </p>
      </div>

      <div>
        <span className="field-label">
          {t('corrAreaTitle')} <span className="text-red-700">*</span>
        </span>
        <p className="mb-2 text-sm text-slate-600">{t('corrAreaHelp')}</p>
        <LocationPicker value={point} onChange={setPoint} />
        {point && (
          <p className="mt-2 text-sm text-slate-700">
            Saved as <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono">{encodeGeohash(point.lat, point.lng)}</code>{' '}
            — an area {GEOHASH_CELL_DESCRIPTION}.
          </p>
        )}
      </div>

      {progress !== null && (
        <div>
          <div
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={processing ? t('processing') : t('submitting')}
            className="h-2 w-full overflow-hidden rounded-full bg-slate-200"
          >
            <div
              className={`h-full bg-civic-600 transition-all ${processing ? 'animate-pulse' : ''}`}
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-1 text-sm text-slate-700" aria-live="polite">
            {processing ? t('processingHelp') : `${t('submitting')} ${progress}%`}
          </p>
        </div>
      )}

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      <button type="submit" className="btn-primary" disabled={!file || !point || progress !== null}>
        {progress === null ? t('submit') : processing ? t('processing') : t('submitting')}
      </button>
    </form>
  )
}
