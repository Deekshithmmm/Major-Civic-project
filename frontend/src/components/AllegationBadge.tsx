import type { PublicStatusBadge } from '../lib/api'
import { useI18n, type StringKey } from '../lib/i18n'

/**
 * Every published report carries one of these (spec 2.3). "Unverified allegation" is the default
 * and stays until an oversight body actually acts, so nothing on the feed reads as a finding.
 */
const STYLES: Record<PublicStatusBadge, string> = {
  unverified_allegation: 'bg-slate-200 text-slate-900',
  under_investigation: 'bg-amber-200 text-amber-900',
  action_taken: 'bg-emerald-200 text-emerald-900',
  dismissed: 'bg-slate-300 text-slate-800',
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
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${STYLES[badge]}`}>
      {t(LABELS[badge])}
    </span>
  )
}
