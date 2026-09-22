import type { IssueStatus } from '../lib/api'
import { useI18n, type StringKey } from '../lib/i18n'

const STYLES: Record<IssueStatus, string> = {
  reported: 'bg-slate-100 text-slate-800 ring-1 ring-slate-300/70',
  acknowledged: 'bg-sky-50 text-sky-900 ring-1 ring-sky-300/70',
  in_progress: 'bg-amber-50 text-amber-900 ring-1 ring-amber-300/70',
  resolved: 'bg-emerald-50 text-emerald-900 ring-1 ring-emerald-300/70',
  overdue: 'bg-red-50 text-red-900 ring-1 ring-red-300/70',
}

const LABEL_KEYS: Record<IssueStatus, StringKey> = {
  reported: 'statusReported',
  acknowledged: 'statusAcknowledged',
  in_progress: 'statusInProgress',
  resolved: 'statusResolved',
  overdue: 'statusOverdue',
}

export default function StatusBadge({ status }: { status: IssueStatus }) {
  const { t } = useI18n()
  return (
    <span className={`pill ${STYLES[status]}`}>
      <span aria-hidden className="pill-dot" />
      {t(LABEL_KEYS[status])}
    </span>
  )
}
