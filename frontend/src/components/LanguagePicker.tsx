import { LANGUAGES, useI18n, type Lang } from '../lib/i18n'

export default function LanguagePicker() {
  const { lang, setLang, t } = useI18n()

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="lang-select" className="text-sm text-slate-700">
        {t('language')}
      </label>
      <select
        id="lang-select"
        value={lang}
        onChange={(e) => setLang(e.target.value as Lang)}
        className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label}
          </option>
        ))}
      </select>
    </div>
  )
}
