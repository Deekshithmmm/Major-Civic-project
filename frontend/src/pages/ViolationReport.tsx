import { useEffect, useState } from 'react'

import LocationPicker from '../components/LocationPicker'
import {
  ApiError,
  apiGet,
  apiUpload,
  compressImage,
  type ViolationCase,
  type ViolationClass,
} from '../lib/api'
import { useI18n } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

export default function ViolationReport() {
  const { t } = useI18n()
  usePageTitle('Report a violation')
  const [classes, setClasses] = useState<ViolationClass[]>([])
  const [slug, setSlug] = useState('')
  const [point, setPoint] = useState<{ lat: number; lng: number } | null>(null)
  const [file, setFile] = useState<File | null>(null)

  const [progress, setProgress] = useState<number | null>(null)
  const [result, setResult] = useState<ViolationCase | null>(null)
  const [error, setError] = useState<string | null>(null)

  const processing = progress === 100
  const selected = classes.find((c) => c.slug === slug)

  useEffect(() => {
    apiGet<ViolationClass[]>('/api/violations/classes')
      .then((c) => {
        setClasses(c)
        if (c.length) setSlug(c[0].slug)
      })
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
      form.append('violation_class_slug', slug)
      form.append('lat', String(point.lat))
      form.append('lng', String(point.lng))
      form.append('file', prepared)

      const timeout = prepared.type.startsWith('video/') ? 5 * 60_000 : 2 * 60_000
      setResult(await apiUpload<ViolationCase>('/api/violations/citizen/upload', form, setProgress, timeout))
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
        <p className="mt-2 text-sm text-slate-700">{t('violSubmitted')}</p>
        <dl className="mt-4 space-y-1 text-sm">
          <div className="flex gap-2">
            <dt className="text-slate-600">Class:</dt>
            <dd className="font-medium">{result.violation_class_label}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-slate-600">Status:</dt>
            <dd className="font-medium">Pending officer review</dd>
          </div>
        </dl>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="max-w-xl space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ink">{t('violReportTitle')}</h1>
        <p className="mt-1 text-sm text-slate-600">{t('violIntro')}</p>
      </div>

      <div>
        <label htmlFor="viol-class" className="field-label">
          {t('violClass')}
        </label>
        <select id="viol-class" className="field-input" value={slug} onChange={(e) => setSlug(e.target.value)}>
          {classes.map((c) => (
            <option key={c.slug} value={c.slug}>
              {c.label}
            </option>
          ))}
        </select>
        {selected && (
          <p className="mt-1 text-sm text-slate-600">
            {selected.identity_path === 'anpr'
              ? 'If a vehicle is involved, an officer resolves the number plate through the vehicle registry.'
              : 'No vehicle involved, so this becomes an unidentified case: an officer acts on the location.'}
            {selected.statutory_section && ` Cited under ${selected.statutory_section}.`}
          </p>
        )}
      </div>

      <div>
        <label htmlFor="viol-file" className="field-label">
          {t('photo')} <span className="text-red-700">*</span>
        </label>
        <input
          id="viol-file"
          type="file"
          required
          accept="image/jpeg,image/png,image/webp,video/mp4,video/webm"
          className="field-input"
          aria-describedby="viol-file-help"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <p id="viol-file-help" className="mt-1 text-sm text-slate-600">
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
