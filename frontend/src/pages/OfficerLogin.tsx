import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { apiPost, setToken } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

export default function OfficerLogin() {
  const { t } = useI18n()
  usePageTitle('Officer login')
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await apiPost<{ access_token: string }>('/api/auth/login', { email, password })
      setToken(res.access_token)
      navigate('/officer/dashboard')
    } catch {
      setError(t('loginFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} className="max-w-sm space-y-4">
      <h1 className="text-xl font-semibold text-ink">{t('navOfficer')}</h1>
      <p className="text-sm text-slate-600">
        Officials only. Citizens never need an account to report or track an issue.
      </p>

      <div>
        <label htmlFor="email" className="field-label">
          {t('email')}
        </label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          required
          className="field-input"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>

      <div>
        <label htmlFor="password" className="field-label">
          {t('password')}
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          className="field-input"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      <button type="submit" className="btn-primary" disabled={loading}>
        {t('login')}
      </button>

      <p className="text-xs text-slate-500">
        Demo accounts (synthetic): officer.roads@demo.city / engineer.sanitation@demo.city —
        password DevPassword123!
      </p>
    </form>
  )
}
