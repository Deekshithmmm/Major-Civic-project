import { Link } from 'react-router-dom'

import { useI18n } from '../lib/i18n'

type Card = {
  to: string
  title: string
  body: string
  cta: string
  tone: 'civic' | 'amber' | 'red'
}

const TONES = {
  civic: 'border-civic-600/30 bg-civic-50',
  amber: 'border-amber-500/30 bg-amber-50',
  red: 'border-red-500/30 bg-red-50',
}

export default function Home() {
  const { t } = useI18n()

  const cards: Card[] = [
    {
      to: '/infrastructure',
      title: t('infraTitle'),
      body: t('homeInfraBody'),
      cta: t('navBoard'),
      tone: 'civic',
    },
    {
      to: '/corruption',
      title: t('homeCorruptionTitle'),
      body: t('homeCorruptionBody'),
      cta: t('homeCorruptionCta'),
      tone: 'civic',
    },
    {
      to: '/violations/report',
      title: t('homeViolationsTitle'),
      body: t('homeViolationsBody'),
      cta: t('homeViolationsCta'),
      tone: 'amber',
    },
    {
      to: '/emergency',
      title: t('homeEmergencyTitle'),
      body: t('homeEmergencyBody'),
      cta: t('homeEmergencyCta'),
      tone: 'red',
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">{t('appName')}</h1>
        <p className="mt-1 max-w-2xl text-slate-700">{t('homeIntro')}</p>
      </div>

      <ul className="grid gap-4 sm:grid-cols-2">
        {cards.map((card) => (
          <li key={card.to}>
            <Link
              to={card.to}
              className={`flex h-full flex-col rounded-lg border p-4 hover:shadow-sm ${TONES[card.tone]}`}
            >
              <h2 className="font-semibold text-ink">{card.title}</h2>
              <p className="mt-1 flex-1 text-sm text-slate-700">{card.body}</p>
              <span className="mt-3 text-sm font-medium text-civic-700 underline underline-offset-2">
                {card.cta} →
              </span>
            </Link>
          </li>
        ))}
      </ul>

      <p className="text-sm text-slate-600">{t('homeNoAccount')}</p>
    </div>
  )
}
