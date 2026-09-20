import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import InfraQueue from '../components/officer/InfraQueue'
import ModerationQueue from '../components/officer/ModerationQueue'
import VigilancePanel from '../components/officer/VigilancePanel'
import ViolationQueue from '../components/officer/ViolationQueue'
import { apiGet, clearToken, getToken, type CurrentUser } from '../lib/api'
import { useI18n } from '../lib/i18n'

type TabId = 'infra' | 'violations' | 'moderation' | 'vigilance'

/**
 * Which panels a role may open. This mirrors the API's own role checks rather than replacing
 * them - the separation of duties in spec 2.6 (a moderator cannot see Module 1 identity data, a
 * municipal officer cannot see Module 2 reports) is enforced server-side; hiding a tab just
 * avoids showing an official a panel that would only return 403.
 */
const TABS: { id: TabId; label: string; roles: string[] }[] = [
  {
    id: 'infra',
    label: 'Infrastructure',
    roles: ['municipal_officer', 'department_engineer', 'admin'],
  },
  { id: 'violations', label: 'Violations', roles: ['municipal_officer', 'admin'] },
  { id: 'moderation', label: 'Moderation', roles: ['moderator', 'admin'] },
  { id: 'vigilance', label: 'Vigilance', roles: ['vigilance_officer', 'admin'] },
]

export default function OfficerDashboard() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [tab, setTab] = useState<TabId | null>(null)

  useEffect(() => {
    if (!getToken()) {
      navigate('/officer')
      return
    }
    apiGet<CurrentUser>('/api/auth/me')
      .then((u) => {
        setUser(u)
        setTab(TABS.find((x) => x.roles.includes(u.role))?.id ?? null)
      })
      .catch(() => {
        clearToken()
        navigate('/officer')
      })
  }, [navigate])

  const available = user ? TABS.filter((x) => x.roles.includes(user.role)) : []

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-ink">Officer dashboard</h1>
          {user && (
            <p className="text-sm text-slate-600">
              {user.full_name} · {user.role.replace(/_/g, ' ')}
            </p>
          )}
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => {
            clearToken()
            navigate('/officer')
          }}
        >
          {t('logout')}
        </button>
      </div>

      {available.length > 1 && (
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Modules">
          {available.map((x) => (
            <button
              key={x.id}
              type="button"
              role="tab"
              aria-selected={tab === x.id}
              className={tab === x.id ? 'btn-primary' : 'btn-secondary'}
              onClick={() => setTab(x.id)}
            >
              {x.label}
            </button>
          ))}
        </div>
      )}

      {available.length === 0 && user && (
        <p className="card text-slate-700">
          The {user.role.replace(/_/g, ' ')} role has no panel here yet. Module 4 evidence access
          is not built — see the README before building it.
        </p>
      )}

      {tab === 'infra' && <InfraQueue />}
      {tab === 'violations' && <ViolationQueue />}
      {tab === 'moderation' && <ModerationQueue />}
      {tab === 'vigilance' && <VigilancePanel />}
    </div>
  )
}
