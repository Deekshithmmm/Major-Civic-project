import { useState } from 'react'

import { useI18n } from '../lib/i18n'

/**
 * Shows a report's tracking code with a copy button. Safe to render on the public Module 3
 * board (see the note on IssuePublicResponse.tracking_token) - do not reuse this for Module 2
 * or Module 4 tokens, which are the reporter's only protected handle.
 */
export default function TrackingCode({ token, compact = false }: { token: string; compact?: boolean }) {
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(token)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard is unavailable over plain http on some browsers; the code is selectable anyway.
    }
  }

  return (
    <div className={compact ? 'flex flex-wrap items-center gap-2' : 'space-y-1'}>
      {!compact && <p className="field-label mb-0">{t('trackingCodeLabel')}</p>}
      <div className="flex flex-wrap items-center gap-2">
        {compact && <span className="text-xs text-slate-600">{t('trackingCodeLabel')}</span>}
        <code className="select-all break-all rounded bg-slate-100 px-2 py-1 font-mono text-xs">
          {token}
        </code>
        <button
          type="button"
          onClick={copy}
          aria-label={`${t('copy')} ${t('trackingCodeLabel')}`}
          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-800 hover:bg-slate-100"
        >
          {copied ? t('copied') : t('copy')}
        </button>
      </div>
    </div>
  )
}
