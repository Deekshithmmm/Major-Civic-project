import { useEffect, useState } from 'react'

import LocationPicker from '../components/LocationPicker'
import TrackingCode from '../components/TrackingCode'
import {
  ApiError,
  apiGet,
  apiUpload,
  compressImage,
  type IssueCategory,
  type IssueCreateResult,
} from '../lib/api'
import { useI18n } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

type LatLng = { lat: number; lng: number }

export default function ReportIssue() {
  const { t } = useI18n()
  usePageTitle('Report an issue')
  const [categories, setCategories] = useState<IssueCategory[]>([])
  const [categorySlug, setCategorySlug] = useState('')
  const [description, setDescription] = useState('')
  const [phone, setPhone] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [point, setPoint] = useState<LatLng | null>(null)

  const [progress, setProgress] = useState<number | null>(null)
  // Upload done, waiting on the server to strip metadata (and blur faces, for photos).
  const processing = progress === 100
  const [result, setResult] = useState<IssueCreateResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiGet<IssueCategory[]>('/api/infra/categories')
      .then((c) => {
        setCategories(c)
        if (c.length) setCategorySlug(c[0].slug)
      })
      .catch(() => setError(t('errorGeneric')))
  }, [t])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!file || !point) return

    setError(null)
    setProgress(0)
    try {
      const prepared = await compressImage(file)
      const form = new FormData()
      form.append('category_slug', categorySlug)
      if (description) form.append('description', description)
      form.append('lat', String(point.lat))
      form.append('lng', String(point.lng))
      if (phone) form.append('phone_number', phone)
      form.append('file', prepared)

      // Videos usually take under a second, but one in a codec that can't be copied is fully
      // re-encoded on the server, which for a long clip can take minutes.
      const processingTimeoutMs = prepared.type.startsWith('video/') ? 5 * 60_000 : 2 * 60_000
      const created = await apiUpload<IssueCreateResult>(
        '/api/infra/issues',
        form,
        setProgress,
        processingTimeoutMs,
      )
      setResult(created)
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
        {result.merged_into_existing && (
          <p className="mt-2 rounded-md bg-sky-50 p-3 text-sm text-sky-900">{t('mergedNotice')}</p>
        )}
        <div className="mt-4">
          <TrackingCode token={result.tracking_token} label={t('trackingToken')} />
        </div>
        <p className="mt-2 text-sm text-slate-600">{t('trackingHelp')}</p>
        <p className="mt-4 text-sm text-slate-600">
          {t('dueBy')}: {new Date(result.sla_deadline).toLocaleString()}
        </p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-xl space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ink">{t('reportTitle')}</h1>
        <p className="mt-1 text-sm text-slate-600">{t('reportAnonymous')}</p>
      </div>

      <div>
        <label htmlFor="category" className="field-label">
          {t('category')}
        </label>
        <select
          id="category"
          required
          className="field-input"
          value={categorySlug}
          onChange={(e) => setCategorySlug(e.target.value)}
        >
          {categories.map((c) => (
            <option key={c.slug} value={c.slug}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="description" className="field-label">
          {t('description')}
        </label>
        <textarea
          id="description"
          rows={3}
          className="field-input"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div>
        <label htmlFor="file" className="field-label">
          {t('photo')} <span className="text-red-700">*</span>
        </label>
        <input
          id="file"
          type="file"
          required
          accept="image/jpeg,image/png,image/webp,video/mp4,video/webm"
          className="field-input"
          aria-describedby="file-help"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <p id="file-help" className="mt-1 text-sm text-slate-600">
          {t('photoHelp')}
        </p>
      </div>

      <div>
        <span className="field-label">
          {t('location')} <span className="text-red-700">*</span>
        </span>
        <p className="mb-2 text-sm text-slate-600">{t('locationHelp')}</p>
        <LocationPicker value={point} onChange={setPoint} />
      </div>

      <div>
        <label htmlFor="phone" className="field-label">
          {t('phoneOptional')}
        </label>
        <input
          id="phone"
          type="tel"
          className="field-input"
          aria-describedby="phone-help"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        <p id="phone-help" className="mt-1 text-sm text-slate-600">
          {t('phoneHelp')}
        </p>
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
          {processing ? (
            <p className="mt-1 text-sm text-slate-700" aria-live="polite">
              <span className="font-medium">{t('processing')}</span> {t('processingHelp')}
            </p>
          ) : (
            <p className="mt-1 text-sm text-slate-600">
              {t('submitting')} {progress}%
            </p>
          )}
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
