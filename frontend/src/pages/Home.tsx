import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import AllegationBadge from '../components/AllegationBadge'
import {
  IconArrowRight,
  IconBribe,
  IconCamera,
  IconLedger,
  IconRoad,
  IconShield,
  IconSiren,
} from '../components/icons'
import ReportMedia from '../components/ReportMedia'
import StatusBadge from '../components/StatusBadge'
import { apiGet, type FeedItem, type Issue } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

type Tone = 'civic' | 'amber' | 'red'

type Card = {
  to: string
  title: string
  body: string
  cta: string
  tone: Tone
  icon: (props: { className?: string }) => JSX.Element
}

// Border and icon colour per section, so the four are distinguishable at a glance - and each
// also carries its own icon, so the distinction does not rest on colour alone.
const TONES: Record<Tone, { card: string; icon: string }> = {
  civic: { card: 'border-civic-600/25 hover:border-civic-500/60', icon: 'bg-civic-100 text-civic-700' },
  amber: { card: 'border-amber-500/25 hover:border-amber-500/60', icon: 'bg-amber-100 text-amber-800' },
  red: { card: 'border-red-500/25 hover:border-red-500/60', icon: 'bg-red-100 text-red-800' },
}

type ViolationStats = {
  pending_review: number
  confirmed: number
  dismissed: number
  challans_issued: number
}

type LedgerRow = { reports_30d: number; unacknowledged_past_sla: number; firs_registered: number }

/**
 * A public case is one of the two things the public is allowed to see: a civic infrastructure
 * report, or a corruption report a moderator has published. Violation evidence and anything from
 * Module 4 are deliberately absent - see the "not shown" section rendered below.
 */
type PublicCase =
  | { kind: 'infra'; at: string; issue: Issue }
  | { kind: 'corruption'; at: string; item: FeedItem }

export default function Home() {
  const { t } = useI18n()
  usePageTitle('Home')
  const [issues, setIssues] = useState<Issue[]>([])
  const [feed, setFeed] = useState<FeedItem[]>([])
  const [violations, setViolations] = useState<ViolationStats | null>(null)
  const [ledger, setLedger] = useState<LedgerRow[]>([])

  useEffect(() => {
    apiGet<Issue[]>('/api/infra/issues').then(setIssues).catch(() => undefined)
    apiGet<FeedItem[]>('/api/corruption/feed').then(setFeed).catch(() => undefined)
    apiGet<ViolationStats>('/api/violations/stats').then(setViolations).catch(() => undefined)
    apiGet<LedgerRow[]>('/api/emergency/ledger').then(setLedger).catch(() => undefined)
  }, [])

  const cases = useMemo<PublicCase[]>(() => {
    const merged: PublicCase[] = [
      ...issues.map((issue) => ({ kind: 'infra' as const, at: issue.created_at, issue })),
      ...feed.map((item) => ({ kind: 'corruption' as const, at: item.created_at, item })),
    ]
    return merged.sort((a, b) => b.at.localeCompare(a.at))
  }, [issues, feed])

  const unacknowledged = ledger.reduce((sum, row) => sum + row.unacknowledged_past_sla, 0)

  const cards: Card[] = [
    { to: '/infrastructure', title: t('infraTitle'), body: t('homeInfraBody'), cta: t('navBoard'), tone: 'civic', icon: IconRoad },
    { to: '/corruption', title: t('homeCorruptionTitle'), body: t('homeCorruptionBody'), cta: t('homeCorruptionCta'), tone: 'civic', icon: IconBribe },
    { to: '/violations/report', title: t('homeViolationsTitle'), body: t('homeViolationsBody'), cta: t('homeViolationsCta'), tone: 'amber', icon: IconCamera },
    { to: '/emergency', title: t('homeEmergencyTitle'), body: t('homeEmergencyBody'), cta: t('homeEmergencyCta'), tone: 'red', icon: IconSiren },
  ]

  const stats = [
    { label: t('homeStatInfra'), value: issues.length, to: '/infrastructure', icon: IconRoad },
    { label: t('homeStatCorruption'), value: feed.length, to: '/corruption', icon: IconBribe },
    { label: t('homeStatViolations'), value: violations?.pending_review ?? '—', to: '/violations/report', icon: IconCamera },
    { label: t('homeStatEmergency'), value: unacknowledged, to: '/transparency', icon: IconLedger },
  ]

  return (
    <div className="space-y-8">
      <section className="hero">
        <div className="relative max-w-2xl">
          <span className="pill bg-civic-100 text-civic-800">
            <IconShield className="h-3.5 w-3.5" />
            {t('heroBadge')}
          </span>
          <h1 className="mt-3 text-3xl font-semibold text-ink sm:text-4xl">{t('appName')}</h1>
          <p className="mt-2 text-slate-700">{t('homeIntro')}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link to="/report" className="btn-primary">
              {t('navReport')}
              <IconArrowRight />
            </Link>
            <Link to="/track" className="btn-secondary">
              {t('navTrack')}
            </Link>
          </div>
        </div>
      </section>

      {/* The four modules come first. They are what someone arrives here to use; the counters
          below are context, and putting them above pushed the actual sections off the screen. */}
      <section>
        <h2 className="text-xl font-semibold text-ink">{t('homeModulesTitle')}</h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">{t('homeModulesIntro')}</p>

        <ul className="mt-4 grid gap-4 sm:grid-cols-2">
          {cards.map((card) => (
            <li key={card.to}>
              <Link
                to={card.to}
                className={`group flex h-full flex-col rounded-xl border bg-white p-5 shadow-card transition-all hover:-translate-y-0.5 hover:shadow-lift ${TONES[card.tone].card}`}
              >
                <div className="flex items-center gap-3">
                  <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-lg ${TONES[card.tone].icon}`}>
                    <card.icon />
                  </span>
                  <h3 className="font-semibold text-ink">{card.title}</h3>
                </div>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-slate-700">{card.body}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-civic-700">
                  {card.cta}
                  <IconArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-xl font-semibold text-ink">{t('homeNumbersTitle')}</h2>
        <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => (
            <li key={stat.label}>
              <Link to={stat.to} className="stat-tile">
                <span className="flex items-start justify-between gap-2">
                  <span className="text-3xl font-semibold text-ink">{stat.value}</span>
                  <span className="grid h-8 w-8 place-items-center rounded-lg bg-slate-100 text-slate-500">
                    <stat.icon className="h-4 w-4" />
                  </span>
                </span>
                <span className="mt-2 block text-xs leading-snug text-slate-600">{stat.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-xl font-semibold text-ink">{t('homeCasesTitle')}</h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">{t('homeCasesIntro')}</p>

        {cases.length === 0 ? (
          <p className="mt-3 text-slate-600">{t('homeCasesEmpty')}</p>
        ) : (
          <ul className="mt-4 space-y-4">
            {cases.map((entry) =>
              entry.kind === 'infra' ? (
                <li key={`infra-${entry.issue.id}`} className="card space-y-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <span className="text-xs font-medium uppercase tracking-wide text-civic-700">
                        {t('infraTitle')}
                      </span>
                      <p className="font-semibold text-ink">{entry.issue.category_label}</p>
                      {entry.issue.description && (
                        <p className="text-sm text-slate-700">{entry.issue.description}</p>
                      )}
                      <p className="mt-1 text-xs text-slate-600">
                        {new Date(entry.issue.created_at).toLocaleString()} · {t('dueBy')}{' '}
                        {new Date(entry.issue.sla_deadline).toLocaleDateString()}
                        {entry.issue.upvote_count > 1 && (
                          <>
                            {' · '}
                            {t('reportedTimes')} {entry.issue.upvote_count} {t('people')}
                          </>
                        )}
                      </p>
                    </div>
                    <StatusBadge status={entry.issue.status} />
                  </div>

                  {entry.issue.media_id && (
                    <ReportMedia
                      mediaId={entry.issue.media_id}
                      kind={entry.issue.media_kind}
                      label={`Submitted ${entry.issue.media_kind === 'video' ? 'video' : 'photo'} of the reported ${entry.issue.category_label}`}
                      className="max-h-72 w-full"
                    />
                  )}

                  <Link
                    to={`/issues/${entry.issue.id}`}
                    className="inline-block text-sm font-medium text-civic-700 underline underline-offset-2"
                  >
                    {t('homeOpenCase')} →
                  </Link>
                </li>
              ) : (
                <li key={`corr-${entry.item.id}`} className="card space-y-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <span className="text-xs font-medium uppercase tracking-wide text-civic-700">
                        {t('homeCorruptionTitle')}
                      </span>
                      <p className="font-semibold text-ink">{entry.item.accused_department}</p>
                      <p className="text-sm text-slate-700">{entry.item.accused_designation}</p>
                      <p className="mt-1 text-xs text-slate-600">
                        {new Date(entry.item.created_at).toLocaleString()} · area {entry.item.geohash}
                      </p>
                    </div>
                    <AllegationBadge badge={entry.item.public_status_badge} />
                  </div>

                  <ReportMedia
                    mediaId={entry.item.media_id}
                    kind={entry.item.media_kind}
                    label={`Evidence submitted about ${entry.item.accused_designation}, ${entry.item.accused_department}`}
                    className="max-h-72 w-full"
                  />

                  {entry.item.description && <p className="text-sm text-slate-700">{entry.item.description}</p>}

                  <Link to="/corruption" className="inline-block text-sm font-medium text-civic-700 underline underline-offset-2">
                    {t('homeOpenCase')} →
                  </Link>
                </li>
              ),
            )}
          </ul>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <h2 className="font-semibold text-ink">{t('homeNotShownTitle')}</h2>
        <ul className="mt-2 space-y-2 text-sm text-slate-700">
          <li>{t('homeNotShownViolations')}</li>
          <li>{t('homeNotShownCrime')}</li>
        </ul>
        <Link
          to="/transparency"
          className="mt-3 inline-block text-sm font-medium text-civic-700 underline underline-offset-2"
        >
          {t('homeSeeLedger')} →
        </Link>
      </section>

      <p className="text-sm text-slate-600">{t('homeNoAccount')}</p>
    </div>
  )
}
