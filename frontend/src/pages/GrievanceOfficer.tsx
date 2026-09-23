import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ErrorNote, Loading } from '../components/Feedback'
import { IconClock, IconShield } from '../components/icons'
import { apiGet, type GrievanceCompliance, type GrievanceOfficer as Officer, type GrievanceTicket } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

/**
 * The page Rule 3(2)(a) of the IT Rules 2021 actually requires: who the Grievance Officer is,
 * how to reach them, and by when they must answer.
 *
 * It carries the platform's own compliance figures for the same reason the transparency page
 * carries a station's - a deadline nobody counts is a deadline nobody keeps, and it would be a
 * strange thing to publish a police station's missed SLAs while quietly not publishing our own.
 */
export default function GrievanceOfficerPage() {
  const { t } = useI18n()
  usePageTitle('Grievance Officer')
  const [officer, setOfficer] = useState<Officer | null>(null)
  const [compliance, setCompliance] = useState<GrievanceCompliance | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [ticketInput, setTicketInput] = useState('')
  const [ticket, setTicket] = useState<GrievanceTicket | null>(null)
  const [ticketError, setTicketError] = useState<string | null>(null)
  const [looking, setLooking] = useState(false)

  useEffect(() => {
    apiGet<Officer>('/api/corruption/grievance-officer')
      .then(setOfficer)
      .catch(() => setError(t('errorGeneric')))
    apiGet<GrievanceCompliance>('/api/corruption/compliance')
      .then(setCompliance)
      .catch(() => undefined)
  }, [t])

  async function lookUp(e: React.FormEvent) {
    e.preventDefault()
    setLooking(true)
    setTicket(null)
    setTicketError(null)
    try {
      setTicket(await apiGet<GrievanceTicket>(`/api/corruption/grievances/track/${ticketInput.trim()}`))
    } catch {
      setTicketError(t('grievanceNotFound'))
    } finally {
      setLooking(false)
    }
  }

  if (error) return <ErrorNote message={error} />
  if (!officer) return <Loading rows={3} />

  return (
    <div className="space-y-8">
      <div className="hero">
        <span className="pill bg-civic-100 text-civic-800">
          <IconShield className="h-3.5 w-3.5" />
          {t('grievanceTitle')}
        </span>
        <h1 className="mt-3 text-2xl font-semibold text-ink sm:text-3xl">{officer.name}</h1>
        <p className="text-sm text-slate-700">{officer.designation}</p>
        <p className="mt-3 max-w-2xl text-slate-700">{t('grievanceIntro')}</p>
      </div>

      <section className="grid gap-3 sm:grid-cols-2">
        <div className="card">
          <p className="text-xs uppercase tracking-wide text-slate-600">{t('grievanceOfficerLabel')}</p>
          <a
            href={`mailto:${officer.email}`}
            className="font-medium text-civic-700 underline underline-offset-2 break-all"
          >
            {officer.email}
          </a>
          <p className="mt-3 text-xs uppercase tracking-wide text-slate-600">{t('grievanceAddress')}</p>
          <p className="text-sm text-slate-800">{officer.address}</p>
        </div>

        <div className="card">
          <div className="flex items-center gap-2 text-slate-800">
            <IconClock className="h-4 w-4" />
            <span className="text-sm font-medium">{t('grievanceAckClock')}</span>
            <span className="ml-auto text-lg font-semibold text-ink">
              {officer.acknowledgement_deadline_hours} {t('grievanceHours')}
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2 text-slate-800">
            <IconClock className="h-4 w-4" />
            <span className="text-sm font-medium">{t('grievanceResolveClock')}</span>
            <span className="ml-auto text-lg font-semibold text-ink">
              {officer.resolution_deadline_days} {t('grievanceDays')}
            </span>
          </div>
          <p className="mt-3 text-xs text-slate-600">{t('grievanceRuleNote')}</p>
        </div>
      </section>

      <section>
        <h2 className="font-semibold text-ink">{t('grievanceComplianceTitle')}</h2>
        <p className="mb-3 text-sm text-slate-600">{t('grievanceComplianceIntro')}</p>

        {compliance && (
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Tile label={t('grievanceReceived')} value={compliance.grievances_received} />
            <Tile
              label={t('grievanceAckMissed')}
              value={compliance.acknowledgement_deadline_missed}
              tone={compliance.acknowledgement_deadline_missed > 0 ? 'bad' : undefined}
            />
            <Tile
              label={t('grievanceOnTime')}
              value={
                compliance.on_time_resolution_rate === null
                  ? '—'
                  : `${Math.round(compliance.on_time_resolution_rate * 100)}%`
              }
            />
            <Tile
              label={t('grievanceOverdue')}
              value={compliance.open_past_deadline}
              tone={compliance.open_past_deadline > 0 ? 'bad' : undefined}
            />
            <Tile label={t('grievanceUpheld')} value={compliance.upheld} />
            <Tile label={t('grievanceRejected')} value={compliance.rejected} />
          </dl>
        )}
      </section>

      <section className="card">
        <h2 className="font-semibold text-ink">{t('grievanceTrackTitle')}</h2>
        <form onSubmit={lookUp} className="mt-2 space-y-2">
          <label className="field-label" htmlFor="ticket">
            {t('grievanceTicketLabel')}
          </label>
          <div className="flex flex-wrap gap-2">
            <input
              id="ticket"
              className="field-input max-w-[16rem] font-mono tracking-widest"
              inputMode="numeric"
              value={ticketInput}
              onChange={(e) => setTicketInput(e.target.value)}
              placeholder="12345678"
            />
            <button type="submit" className="btn-primary" disabled={looking || !ticketInput.trim()}>
              {t('grievanceTrackTitle')}
            </button>
          </div>
          <p className="text-xs text-slate-600">{t('grievanceTicketHelp')}</p>
        </form>

        {ticketError && (
          <p className="mt-3">
            <ErrorNote message={ticketError} />
          </p>
        )}

        {ticket && (
          <dl className="mt-4 space-y-1 border-t border-slate-200 pt-3 text-sm" role="status">
            <div className="flex gap-2">
              <dt className="w-40 shrink-0 text-slate-600">{t('grievanceDecision')}</dt>
              <dd className="font-medium capitalize">{ticket.status}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-40 shrink-0 text-slate-600">{t('grievanceDueBy')}</dt>
              <dd className={ticket.overdue ? 'font-medium text-red-800' : ''}>
                {new Date(ticket.resolution_due_by).toLocaleDateString()}
                {ticket.overdue && ` · ${t('grievancePastDue')}`}
              </dd>
            </div>
            {ticket.resolution_note && (
              <div className="flex gap-2">
                <dt className="w-40 shrink-0 text-slate-600">{t('grievanceDecision')}</dt>
                <dd className="text-slate-800">{ticket.resolution_note}</dd>
              </div>
            )}
          </dl>
        )}
      </section>

      <p className="text-sm text-slate-600">
        <Link to="/corruption" className="font-medium text-civic-700 underline underline-offset-2">
          {t('corrFeedTitle')} →
        </Link>
      </p>
    </div>
  )
}

function Tile({ label, value, tone }: { label: string; value: string | number; tone?: 'bad' }) {
  return (
    <div className="stat-tile">
      <dt className="text-xs text-slate-600">{label}</dt>
      <dd className={`mt-1 text-2xl font-semibold ${tone === 'bad' ? 'text-red-800' : 'text-ink'}`}>{value}</dd>
    </div>
  )
}
