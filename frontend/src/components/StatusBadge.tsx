import type { IssueStatus } from '../lib/api'
import { useI18n, type StringKey } from '../lib/i18n'

const STYLES: Record<IssueStatus, string> = {
  reported: 'bg-slate-200 text-slate-900',
  acknowledged: 'bg-sky-200 text-sky-900',
  in_progress: 'bg-amber-200 text-amber-900',
  resolved: 'bg-emerald-200 text-emerald-900',
  overdue: 'bg-red-200 text-red-900',
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
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${STYLES[status]}`}>
      {t(LABEL_KEYS[status])}
    </span>
  )
}
