import { NavLink, Route, Routes } from 'react-router-dom'

import LanguagePicker from './components/LanguagePicker'
import IssueDetail from './pages/IssueDetail'
import OfficerDashboard from './pages/OfficerDashboard'
import OfficerLogin from './pages/OfficerLogin'
import ReportIssue from './pages/ReportIssue'
import StatusBoard from './pages/StatusBoard'
import TrackIssue from './pages/TrackIssue'
import { useI18n } from './lib/i18n'

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `rounded-md px-3 py-2 text-sm font-medium ${
          isActive ? 'bg-civic-600 text-white' : 'text-slate-700 hover:bg-slate-200'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

export default function App() {
  const { t } = useI18n()

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-2 px-4 py-3">
          <span className="mr-auto text-lg font-semibold text-ink">{t('appName')}</span>
          <nav aria-label="Main" className="flex flex-wrap items-center gap-1">
            <NavItem to="/" label={t('navBoard')} />
            <NavItem to="/report" label={t('navReport')} />
            <NavItem to="/track" label={t('navTrack')} />
            <NavItem to="/officer" label={t('navOfficer')} />
          </nav>
          <LanguagePicker />
        </div>
      </header>

      <main id="main" className="mx-auto max-w-5xl px-4 py-6">
        <Routes>
          <Route path="/" element={<StatusBoard />} />
          <Route path="/report" element={<ReportIssue />} />
          <Route path="/track" element={<TrackIssue />} />
          <Route path="/issues/:issueId" element={<IssueDetail />} />
          <Route path="/officer" element={<OfficerLogin />} />
          <Route path="/officer/dashboard" element={<OfficerDashboard />} />
        </Routes>
      </main>

      <footer className="mx-auto max-w-5xl px-4 py-8 text-xs text-slate-600">
        <p>
          Demo build on synthetic data. Citizens never need an account. Reports are anonymous by
          default; location data is stripped from every file before it is stored, and faces are
          blurred in photos (not in videos).
        </p>
      </footer>
    </div>
  )
}
