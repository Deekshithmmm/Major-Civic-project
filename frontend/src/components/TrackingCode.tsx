import { useState } from 'react'

import { useI18n } from '../lib/i18n'

/**
 * A 10-digit code reads far more easily in groups, the way a phone number does. Codes created
 * before the numeric format (random strings) are shown unchanged. The copy button always copies
 * the raw code, and the lookup endpoint ignores spacing, so either form works when pasted back.
 */
function forDisplay(code: string): string {
  return /^\d{10}$/.test(code) ? `${code.slice(0, 4)} ${code.slice(4, 7)} ${code.slice(7)}` : code
}

/**
 * Shows a report's tracking code with a copy button. Safe to render on the public Module 3
 * board (see the note on IssuePublicResponse.tracking_token) - do not reuse this for Module 2
 * or Module 4 tokens, which are the reporter's only protected handle.
 */
export default function TrackingCode({
  token,
  compact = false,
  label,
}: {
  token: string
  compact?: boolean
  label?: string
}) {
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)
  const caption = label ?? t('trackingCodeLabel')

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
      {!compact && <p className="field-label mb-0">{caption}</p>}
      <div className="flex flex-wrap items-center gap-2">
        {compact && <span className="text-xs text-slate-600">{caption}</span>}
        <code
          className={`select-all break-all rounded bg-slate-100 px-2 py-1 font-mono tracking-wide ${
            compact ? 'text-xs' : 'text-base font-semibold'
          }`}
        >
          {forDisplay(token)}
        </code>
        <button
          type="button"
          onClick={copy}
          aria-label={`${t('copy')} ${caption}`}
          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-800 hover:bg-slate-100"
        >
          {copied ? t('copied') : t('copy')}
        </button>
      </div>
    </div>
  )
}
