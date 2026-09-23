import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ErrorNote } from '../components/Feedback'
import { IconAlert, IconShield } from '../components/icons'
import { apiPost, type GrievanceGround, type GrievanceResult } from '../lib/api'
import { useI18n, type StringKey } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

const GROUNDS: { value: GrievanceGround; label: StringKey }[] = [
  { value: 'factually_incorrect', label: 'groundFactuallyIncorrect' },
  { value: 'identifies_private_person', label: 'groundIdentifiesPrivatePerson' },
  { value: 'defamatory', label: 'groundDefamatory' },
  { value: 'sub_judice', label: 'groundSubJudice' },
  { value: 'not_my_department', label: 'groundNotMyDepartment' },
  { value: 'other', label: 'groundOther' },
]

/**
 * The two things the body an allegation concerns can do about it, side by side, because they are
 * routinely confused and they are not the same remedy:
 *
 *   - A reply is published under the allegation and leaves it standing. It is the proportionate
 *     answer to "this is misleading", and it costs the reader nothing - they see both.
 *   - A grievance asks for the report to come down. It is the remedy the IT Rules require, and
 *     it is the stronger one, so it asks for a named complainant and a specific ground.
 *
 * Offering only the second would make removal the only available response to criticism.
 */
export default function RespondToReport() {
  const { reportId } = useParams()
  const { t } = useI18n()
  usePageTitle('Respond to a report')
  const [tab, setTab] = useState<'reply' | 'grievance'>('reply')

  return (
    <div className="space-y-5">
      <div>
        <Link to="/corruption" className="text-sm text-civic-700 underline underline-offset-2">
          ← {t('corrFeedTitle')}
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-ink">{t('respondTitle')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-700">{t('respondIntro')}</p>
      </div>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label={t('respondTitle')}>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'reply'}
          className={tab === 'reply' ? 'btn-primary' : 'btn-secondary'}
          onClick={() => setTab('reply')}
        >
          {t('replyTab')}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'grievance'}
          className={tab === 'grievance' ? 'btn-primary' : 'btn-secondary'}
          onClick={() => setTab('grievance')}
        >
          {t('grievanceTab')}
        </button>
      </div>

      {!reportId ? (
        <ErrorNote message={t('errorGeneric')} />
      ) : tab === 'reply' ? (
        <ReplyForm reportId={reportId} />
      ) : (
        <GrievanceForm reportId={reportId} />
      )}
    </div>
  )
}

function ReplyForm({ reportId }: { reportId: string }) {
  const { t } = useI18n()
  const [body, setBody] = useState('')
  const [department, setDepartment] = useState('')
  const [designation, setDesignation] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await apiPost('/api/corruption/replies', {
        report_id: reportId,
        body,
        author_department: department,
        author_designation: designation,
        author_name: name,
        author_contact_email: email,
      })
      setDone(true)
    } catch {
      setError(t('errorGeneric'))
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="card border-emerald-200 bg-emerald-50" role="status">
        <p className="font-medium text-emerald-900">{t('replySubmitted')}</p>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="card space-y-4">
      <p className="text-sm text-slate-700">{t('replyIntro')}</p>
      {error && <ErrorNote message={error} />}

      <div>
        <label className="field-label" htmlFor="reply-body">
          {t('replyBody')}
        </label>
        <textarea
          id="reply-body"
          required
          minLength={20}
          rows={5}
          className="field-input"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="field-label" htmlFor="reply-dept">
            {t('replyDepartment')}
          </label>
          <input
            id="reply-dept"
            required
            className="field-input"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="reply-desig">
            {t('replyDesignation')}
          </label>
          <input
            id="reply-desig"
            required
            className="field-input"
            value={designation}
            onChange={(e) => setDesignation(e.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="reply-name">
            {t('replyAuthor')}
          </label>
          <input
            id="reply-name"
            required
            className="field-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="reply-email">
            {t('replyEmail')}
          </label>
          <input
            id="reply-email"
            required
            type="email"
            className="field-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
      </div>

      <button type="submit" className="btn-primary" disabled={busy}>
        {busy ? t('submitting') : t('replySubmit')}
      </button>
    </form>
  )
}

function GrievanceForm({ reportId }: { reportId: string }) {
  const { t } = useI18n()
  const [ground, setGround] = useState<GrievanceGround>('factually_incorrect')
  const [body, setBody] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [designation, setDesignation] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<GrievanceResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setResult(
        await apiPost<GrievanceResult>('/api/corruption/grievances', {
          report_id: reportId,
          ground,
          body,
          complainant_name: name,
          complainant_email: email,
          complainant_designation: designation || null,
        }),
      )
    } catch {
      setError(t('errorGeneric'))
    } finally {
      setBusy(false)
    }
  }

  if (result) {
    return (
      <div className="card border-emerald-200 bg-emerald-50" role="status">
        <p className="font-medium text-emerald-900">{t('grievanceSubmitted')}</p>
        <p className="mt-2 font-mono text-2xl font-semibold tracking-widest text-emerald-900">
          {result.ticket}
        </p>
        <p className="mt-2 text-sm text-emerald-900">
          {t('grievanceDueBy')}: {new Date(result.resolution_due_by).toLocaleDateString()}
        </p>
        <Link
          to="/corruption/grievance"
          className="mt-3 inline-block text-sm font-medium text-civic-700 underline underline-offset-2"
        >
          {t('grievanceTrackTitle')} →
        </Link>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="card space-y-4">
      <p className="flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
        <IconAlert className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{t('grievanceBodyHelp')}</span>
      </p>
      {error && <ErrorNote message={error} />}

      <fieldset>
        <legend className="field-label">{t('grievanceGround')}</legend>
        <div className="space-y-1.5">
          {GROUNDS.map((g) => (
            <label key={g.value} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="ground"
                value={g.value}
                checked={ground === g.value}
                onChange={() => setGround(g.value)}
              />
              {t(g.label)}
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <label className="field-label" htmlFor="griev-body">
          {t('grievanceBody')}
        </label>
        <textarea
          id="griev-body"
          required
          minLength={20}
          rows={5}
          className="field-input"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="field-label" htmlFor="griev-name">
            {t('grievanceName')}
          </label>
          <input
            id="griev-name"
            required
            className="field-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="griev-desig">
            {t('grievanceDesignation')}
          </label>
          <input
            id="griev-desig"
            className="field-input"
            value={designation}
            onChange={(e) => setDesignation(e.target.value)}
          />
        </div>
      </div>

      <div>
        <label className="field-label" htmlFor="griev-email">
          {t('grievanceEmail')}
        </label>
        <input
          id="griev-email"
          required
          type="email"
          className="field-input"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <p className="mt-1 text-xs text-slate-600">{t('grievanceEmailHelp')}</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? t('submitting') : t('grievanceSubmit')}
        </button>
        <Link
          to="/corruption/grievance"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-civic-700 underline underline-offset-2"
        >
          <IconShield className="h-4 w-4" />
          {t('grievanceTitle')}
        </Link>
      </div>
    </form>
  )
}
