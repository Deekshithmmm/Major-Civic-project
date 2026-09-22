import { useEffect, useState } from 'react'

import { ErrorNote } from '../components/Feedback'
import { apiGet } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { usePageTitle } from '../lib/usePageTitle'

type LedgerRow = {
  station_id: string
  station_name: string
  station_code: string
  reports_30d: number
  reports_90d: number
  unacknowledged_past_sla: number
  firs_registered: number
  fir_conversion_rate: number | null
  median_ack_hours: number | null
  open_past_fir_sla: number
  closed_without_fir: number
  flagged_red: boolean
}

type CaseRecord = {
  report_id: string
  category: string
  ward_name: string
  reported_on: string
  status: string
  fir_number: string | null
  sections: string | null
  court_name: string | null
  outcome: string | null
}

type HotspotCell = {
  ward_name: string
  quarter: string
  category: string
  report_count: number
  firs_registered: number
}

/**
 * The three public surfaces that replace a feed of crime footage (spec 2.5). The
 * unacknowledged-past-SLA counter is the headline: a station sitting on reports is visible
 * within a day, without publishing a frame of anything.
 */
export default function Transparency() {
  const { t } = useI18n()
  usePageTitle('Accountability')
  const [ledger, setLedger] = useState<LedgerRow[]>([])
  const [hotspots, setHotspots] = useState<HotspotCell[]>([])
  const [cases, setCases] = useState<CaseRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiGet<LedgerRow[]>('/api/emergency/ledger').then(setLedger).catch(() => setError(t('errorGeneric')))
    apiGet<HotspotCell[]>('/api/emergency/hotspots').then(setHotspots).catch(() => undefined)
    apiGet<CaseRecord[]>('/api/emergency/cases').then(setCases).catch(() => undefined)
  }, [t])

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-ink">{t('navTransparency')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-700">
          Crime reports and their evidence are never published here. What is published is how each
          station responds to them — which makes inaction visible without warning anyone, tainting
          identification evidence, or exposing the person who reported it.
        </p>
      </div>

      {error && <ErrorNote message={error} />}

      <section>
        <h2 className="font-semibold text-ink">Station response ledger</h2>
        <p className="mb-3 text-sm text-slate-600">
          A station is flagged when a report is past seven days with no FIR. Under{' '}
          <em>Lalita Kumari</em> (2014), registering an FIR is mandatory where the information
          discloses a cognizable offence, so a low conversion rate is a legal question rather than
          an opinion.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[46rem] border-collapse text-sm">
            <caption className="sr-only">Police station response metrics</caption>
            <thead>
              <tr className="table-head">
                <th scope="col" className="py-2 pr-3">Station</th>
                <th scope="col" className="py-2 pr-3">Reports (30d)</th>
                <th scope="col" className="py-2 pr-3">Unacknowledged past SLA</th>
                <th scope="col" className="py-2 pr-3">FIRs</th>
                <th scope="col" className="py-2 pr-3">Conversion</th>
                <th scope="col" className="py-2 pr-3">Median ack.</th>
                <th scope="col" className="py-2 pr-3">Closed without FIR</th>
              </tr>
            </thead>
            <tbody>
              {ledger.map((row) => (
                <tr key={row.station_id} className={`border-b border-slate-200 ${row.flagged_red ? 'bg-red-50' : ''}`}>
                  <th scope="row" className="py-2 pr-3 text-left font-medium">
                    {row.station_name}
                    {row.flagged_red && (
                      <span className="ml-2 rounded-full bg-red-200 px-2 py-0.5 text-xs font-semibold text-red-900">
                        Past FIR deadline
                      </span>
                    )}
                  </th>
                  <td className="py-2 pr-3">{row.reports_30d}</td>
                  <td className={`py-2 pr-3 font-semibold ${row.unacknowledged_past_sla > 0 ? 'text-red-800' : ''}`}>
                    {row.unacknowledged_past_sla}
                  </td>
                  <td className="py-2 pr-3">{row.firs_registered}</td>
                  <td className="py-2 pr-3">
                    {row.fir_conversion_rate === null ? '—' : `${Math.round(row.fir_conversion_rate * 100)}%`}
                  </td>
                  <td className="py-2 pr-3">
                    {row.median_ack_hours === null ? '—' : `${row.median_ack_hours}h`}
                  </td>
                  <td className="py-2 pr-3">{row.closed_without_fir}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {ledger.length === 0 && <p className="text-slate-600">No stations reporting yet.</p>}
      </section>

      <section>
        <h2 className="font-semibold text-ink">Hotspot map</h2>
        <p className="mb-3 text-sm text-slate-600">
          Reports per ward per quarter, against FIRs registered in the same cell. It runs a quarter
          behind and hides any cell with fewer than five reports: a live map would be an
          intelligence feed for the people being reported, and a cell of one points at whoever
          filed it.
        </p>

        {hotspots.length === 0 ? (
          <p className="text-slate-600">
            No cell has reached the threshold of five yet, so nothing is shown.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {hotspots.map((cell) => (
              <li key={`${cell.ward_name}-${cell.quarter}-${cell.category}`} className="card">
                <p className="font-medium">{cell.ward_name}</p>
                <p className="text-sm text-slate-700">
                  {cell.category.replace(/_/g, ' ')} · {cell.quarter}
                </p>
                <p className="mt-1 text-sm">
                  <span className="font-semibold">{cell.report_count}</span> reports ·{' '}
                  <span className="font-semibold">{cell.firs_registered}</span> FIRs
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="font-semibold text-ink">Case record</h2>
        <p className="mb-3 text-sm text-slate-600">
          Disclosure is gated on case stage. Before a chargesheet is filed nothing case-specific is
          published beyond category, ward, date and status. Once it is filed the proceedings are
          public record anyway, so the sections and the court appear — and no more. Sexual offence
          and child cases appear here at no stage.
        </p>

        {cases.length === 0 ? (
          <p className="text-slate-600">No cases on the public record yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] border-collapse text-sm">
              <caption className="sr-only">Public case record by stage</caption>
              <thead>
                <tr className="table-head">
                  <th scope="col" className="py-2 pr-3">Offence</th>
                  <th scope="col" className="py-2 pr-3">Ward</th>
                  <th scope="col" className="py-2 pr-3">Reported</th>
                  <th scope="col" className="py-2 pr-3">Stage</th>
                  <th scope="col" className="py-2 pr-3">FIR</th>
                  <th scope="col" className="py-2 pr-3">Court / outcome</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.report_id} className="border-b border-slate-200">
                    <td className="py-2 pr-3">{c.category.replace(/_/g, ' ')}</td>
                    <td className="py-2 pr-3">{c.ward_name}</td>
                    <td className="py-2 pr-3">{c.reported_on}</td>
                    <td className="py-2 pr-3">
                      <span
                        className={`pill ${
                          c.status === 'Chargesheet filed'
                            ? 'bg-emerald-200 text-emerald-900'
                            : c.status === 'Report received'
                              ? 'bg-slate-200'
                              : 'bg-sky-200 text-sky-900'
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="py-2 pr-3">
                      {c.fir_number ? (
                        <>
                          <span className="font-mono text-xs">{c.fir_number}</span>
                          {c.sections && <span className="block text-xs text-slate-600">u/s {c.sections}</span>}
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-2 pr-3">{c.court_name ?? c.outcome ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="font-semibold text-ink">Never published</h2>
        <ul className="mt-1 list-inside list-disc text-sm text-slate-700">
          <li>The footage itself, in any form, blurred or not.</li>
          <li>Names, faces, vehicle numbers or addresses of anyone accused or reported.</li>
          <li>Anything at all from the sexual offence and minor categories, including counts.</li>
          <li>The live location of an open report.</li>
        </ul>
      </section>
    </div>
  )
}
