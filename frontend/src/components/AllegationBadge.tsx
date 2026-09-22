import type { PublicStatusBadge } from '../lib/api'
import { useI18n, type StringKey } from '../lib/i18n'

/**
 * Every published report carries one of these (spec 2.3). "Unverified allegation" is the default
 * and stays until an oversight body actually acts, so nothing on the feed reads as a finding.
 */
const STYLES: Record<PublicStatusBadge, string> = {
  unverified_allegation: 'bg-slate-100 text-slate-800 ring-1 ring-slate-300/70',
  under_investigation: 'bg-amber-50 text-amber-900 ring-1 ring-amber-300/70',
  action_taken: 'bg-emerald-50 text-emerald-900 ring-1 ring-emerald-300/70',
  dismissed: 'bg-slate-100 text-slate-600 ring-1 ring-slate-300/70',
}

const LABELS: Record<PublicStatusBadge, StringKey> = {
  unverified_allegation: 'badgeUnverified',
  under_investigation: 'badgeInvestigating',
  action_taken: 'badgeActionTaken',
  dismissed: 'badgeDismissed',
}

export default function AllegationBadge({ badge }: { badge: PublicStatusBadge }) {
  const { t } = useI18n()
  return (
    <span className={`pill ${STYLES[badge]}`}>
      <span aria-hidden className="pill-dot" />
      {t(LABELS[badge])}
    </span>
  )
}
