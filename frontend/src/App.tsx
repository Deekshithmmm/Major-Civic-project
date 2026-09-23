import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'

import LanguagePicker from './components/LanguagePicker'
import { IconShield } from './components/icons'
import CorruptionFeed from './pages/CorruptionFeed'
import CorruptionReport from './pages/CorruptionReport'
import DatabaseExplorer from './pages/DatabaseExplorer'
import EmergencyTriage from './pages/EmergencyTriage'
import GrievanceOfficerPage from './pages/GrievanceOfficer'
import Home from './pages/Home'
import IssueDetail from './pages/IssueDetail'
import OfficerDashboard from './pages/OfficerDashboard'
import OfficerLogin from './pages/OfficerLogin'
import ReportIssue from './pages/ReportIssue'
import RespondToReport from './pages/RespondToReport'
import StationDetail from './pages/StationDetail'
import Stations from './pages/Stations'
import StatusBoard from './pages/StatusBoard'
import TrackIssue from './pages/TrackIssue'
import Transparency from './pages/Transparency'
import ViolationReport from './pages/ViolationReport'
import { useI18n } from './lib/i18n'

function NavItem({
  to,
  label,
  end = false,
  onNavigate,
}: {
  to: string
  label: string
  end?: boolean
  onNavigate?: () => void
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        `rounded-md px-3 py-2 text-sm font-medium transition-colors ${
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
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  // Eight destinations do not fit a phone header, so they collapse behind a toggle. Closing on
  // navigation keeps the menu from covering the page the reader just asked for.
  useEffect(() => setMenuOpen(false), [location.pathname])

  const links = (
    <>
      <NavItem to="/" label={t('navHome')} end onNavigate={() => setMenuOpen(false)} />
      <NavItem to="/infrastructure" label={t('infraTitle')} onNavigate={() => setMenuOpen(false)} />
      <NavItem to="/corruption" label={t('navCorruption')} onNavigate={() => setMenuOpen(false)} />
      <NavItem to="/violations/report" label={t('navViolations')} onNavigate={() => setMenuOpen(false)} />
      <NavItem to="/emergency" label={t('navEmergency')} onNavigate={() => setMenuOpen(false)} />
      <NavItem to="/stations" label={t('navStations')} onNavigate={() => setMenuOpen(false)} />
      <NavItem to="/transparency" label={t('navTransparency')} onNavigate={() => setMenuOpen(false)} />
      <NavItem to="/database" label={t('navDatabase')} onNavigate={() => setMenuOpen(false)} />
      <NavItem to="/officer" label={t('navOfficer')} onNavigate={() => setMenuOpen(false)} />
    </>
  )

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3">
          <NavLink to="/" className="mr-auto flex items-center gap-2 text-lg font-semibold text-ink">
            <span aria-hidden className="grid h-8 w-8 place-items-center rounded-lg bg-civic-600 text-white shadow-sm">
              <IconShield className="h-5 w-5" />
            </span>
            <span className="hidden sm:inline">{t('appName')}</span>
          </NavLink>

          <nav aria-label="Main" className="hidden flex-wrap items-center gap-1 lg:flex">
            {links}
          </nav>

          <LanguagePicker />

          <button
            type="button"
            className="btn-secondary px-3 py-2 lg:hidden"
            aria-expanded={menuOpen}
            aria-controls="mobile-nav"
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span className="sr-only">{t('menu')}</span>
            <span aria-hidden>{menuOpen ? '✕' : '☰'}</span>
          </button>
        </div>

        {menuOpen && (
          <nav
            id="mobile-nav"
            aria-label="Main"
            className="mx-auto flex max-w-5xl flex-col gap-1 border-t border-slate-200 px-4 py-2 lg:hidden"
          >
            {links}
          </nav>
        )}
      </header>

      <main id="main" className="mx-auto w-full max-w-5xl flex-1 animate-fade-in px-4 py-6">
        <Routes>
          <Route path="/" element={<Home />} />

          {/* Module 3 */}
          <Route path="/infrastructure" element={<StatusBoard />} />
          <Route path="/report" element={<ReportIssue />} />
          <Route path="/track" element={<TrackIssue />} />
          <Route path="/issues/:issueId" element={<IssueDetail />} />

          {/* Module 2 */}
          <Route path="/corruption" element={<CorruptionFeed />} />
          <Route path="/corruption/report" element={<CorruptionReport />} />
          <Route path="/corruption/grievance" element={<GrievanceOfficerPage />} />
          <Route path="/corruption/respond/:reportId" element={<RespondToReport />} />

          {/* Module 1 */}
          <Route path="/violations/report" element={<ViolationReport />} />

          {/* Module 4 and the police station network */}
          <Route path="/emergency" element={<EmergencyTriage />} />
          <Route path="/transparency" element={<Transparency />} />
          <Route path="/stations" element={<Stations />} />
          <Route path="/stations/:stationId" element={<StationDetail />} />

          {/* What the system stores, in plain words. Development only - the API behind it
              refuses to load otherwise and the page explains that rather than erroring. */}
          <Route path="/database" element={<DatabaseExplorer />} />
          <Route path="/database/:tableName" element={<DatabaseExplorer />} />

          {/* Officials */}
          <Route path="/officer" element={<OfficerLogin />} />
          <Route path="/officer/dashboard" element={<OfficerDashboard />} />
        </Routes>
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-4 py-6 text-xs text-slate-600">
          <p>
            Demo build on synthetic data. Citizens never need an account. Reports are anonymous by
            default; location data is stripped from every file before it is stored, and faces are
            blurred in photos (not in videos).
          </p>
          <p className="mt-2">
            If someone is in danger right now, call{' '}
            <a href="tel:112" className="font-semibold text-red-700 underline">
              112
            </a>
            . Childline{' '}
            <a href="tel:1098" className="font-semibold text-red-700 underline">
              1098
            </a>
            . Women’s helpline{' '}
            <a href="tel:181" className="font-semibold text-red-700 underline">
              181
            </a>
            .
          </p>
        </div>
      </footer>
    </div>
  )
}
