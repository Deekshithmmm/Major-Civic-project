import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { EmptyState, ErrorNote, Loading } from '../components/Feedback'
import { IconAlert, IconLedger, IconShield } from '../components/icons'
import {
  ApiError,
  apiGet,
  apiPost,
  type FormField,
  type SchemaOverview,
  type TableDetail,
} from '../lib/api'
import { usePageTitle } from '../lib/usePageTitle'

/**
 * The database, for people who do not read databases.
 *
 * A schema browser answers "what columns exist". Someone being shown this system for the first
 * time is asking something else: what does it keep about me, and can the people running it
 * quietly change it. So every table here is named in plain words, a row is described as a thing
 * rather than a record, identifiers are resolved to the name of what they point at, and the
 * columns deliberately withheld say so on the page along with why.
 *
 * Served only in development - the API behind it refuses to load otherwise, and a 404 is
 * rendered as an explanation rather than an error.
 */
export default function DatabaseExplorer() {
  const { tableName } = useParams()
  usePageTitle('What the system stores')
  return tableName ? <TableView name={tableName} /> : <Overview />
}

function Overview() {
  const [data, setData] = useState<SchemaOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    apiGet<SchemaOverview>('/api/schema/tables')
      .then(setData)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) setUnavailable(true)
        else setError('Could not read the database.')
      })
  }, [])

  if (unavailable) {
    return (
      <EmptyState
        title="This page is only available in development."
        body="It is a readable window onto the database, so it is deliberately not served anywhere else."
      />
    )
  }
  if (error) return <ErrorNote message={error} />
  if (!data) return <Loading rows={4} />

  return (
    <div className="space-y-8">
      <div className="hero">
        <span className="pill bg-civic-100 text-civic-800">
          <IconLedger className="h-3.5 w-3.5" />
          The database
        </span>
        <h1 className="mt-3 text-2xl font-semibold text-ink sm:text-3xl">What the system stores</h1>
        <p className="mt-3 max-w-2xl text-slate-700">
          Everything this platform keeps, in {data.table_count} tables, described in plain words.
          Open any one to see what a single row means, what each column is for, and real examples
          from the running database.
        </p>
      </div>

      {data.undocumented.length > 0 && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <strong>{data.undocumented.length} table(s) have no description yet</strong> —{' '}
          {data.undocumented.join(', ')}. They exist in the database but nobody has written an
          explanation for them, so this page is not showing the whole picture.
        </p>
      )}

      {data.groups.map((group) => (
        <section key={group.key}>
          <h2 className="text-lg font-semibold text-ink">{group.label}</h2>
          <p className="mb-3 max-w-3xl text-sm text-slate-600">{group.blurb}</p>

          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {group.tables.map((t) => (
              <li key={t.name}>
                <Link to={`/database/${t.name}`} className="card-link flex h-full flex-col">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-ink">{t.label}</span>
                    <span className="shrink-0 text-sm font-semibold text-civic-700">
                      {t.row_count.toLocaleString()}
                    </span>
                  </div>
                  <p className="mt-1 flex-1 text-sm text-slate-600">{t.row_is}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {t.append_only && (
                      <span className="pill bg-emerald-50 text-emerald-900 ring-1 ring-emerald-300/70">
                        <span aria-hidden className="pill-dot" />
                        Can never be changed
                      </span>
                    )}
                    {t.has_masked && (
                      <span className="pill bg-slate-100 text-slate-700 ring-1 ring-slate-300/70">
                        <span aria-hidden className="pill-dot" />
                        Some columns hidden
                      </span>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}

      <section className="card bg-slate-50">
        <h2 className="flex items-center gap-2 font-semibold text-ink">
          <IconShield className="h-4 w-4" />
          Why some things are hidden here
        </h2>
        <p className="mt-1 text-sm text-slate-700">
          A page built to make the database understandable must not become the one place where
          every protection in the system is bypassed. Whistleblowers' tracking codes, residents'
          phone numbers, evidence files and complainants' email addresses are never loaded by this
          page at all — not fetched and then hidden. Where a column is withheld, the table says so
          and gives the reason.
        </p>
      </section>
    </div>
  )
}

function TableView({ name }: { name: string }) {
  const [data, setData] = useState<TableDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloads, setReloads] = useState(0)

  useEffect(() => {
    apiGet<TableDetail>(`/api/schema/tables/${name}`)
      .then(setData)
      .catch(() => setError('Could not read that table.'))
  }, [name, reloads])

  if (error) return <ErrorNote message={error} />
  if (!data) return <Loading rows={4} />

  return (
    <div className="space-y-6">
      <div>
        <Link to="/database" className="text-sm text-civic-700 underline underline-offset-2">
          ← What the system stores
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold text-ink">{data.label}</h1>
            <p className="text-sm text-slate-700">{data.row_is}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="pill bg-slate-100 text-slate-700 ring-1 ring-slate-300/70">
              {data.row_count.toLocaleString()} rows
            </span>
            {data.append_only && (
              <span className="pill bg-emerald-50 text-emerald-900 ring-1 ring-emerald-300/70">
                <span aria-hidden className="pill-dot" />
                Can never be changed
              </span>
            )}
          </div>
        </div>
        <p className="mt-3 max-w-3xl text-slate-700">{data.purpose}</p>
        {data.note && (
          <p className="mt-2 flex max-w-3xl items-start gap-2 rounded-lg bg-civic-50/70 p-3 text-sm text-civic-900">
            <IconAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{data.note}</span>
          </p>
        )}
      </div>

      <section>
        <h2 className="font-semibold text-ink">What is kept in each row</h2>
        <ul className="mt-2 grid gap-2 sm:grid-cols-2">
          {data.columns.map((c) => (
            <li key={c.name} className="card py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium text-ink">{c.label}</span>
                <span className="text-xs text-slate-500">
                  {c.points_at ? `→ ${c.points_at}` : c.type}
                  {c.optional && ' · optional'}
                </span>
              </div>
              {c.means && <p className="mt-0.5 text-sm text-slate-600">{c.means}</p>}
            </li>
          ))}
        </ul>
      </section>

      {data.withheld.length > 0 && (
        <section className="card border-amber-200 bg-amber-50">
          <h2 className="font-semibold text-amber-900">Not shown on this page</h2>
          <ul className="mt-1 space-y-1 text-sm text-amber-900">
            {data.withheld.map((w) => (
              <li key={w.column}>
                <strong>{w.column.replace(/_/g, ' ')}</strong> — {w.reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.editable && <CreateRow table={data} onCreated={() => setReloads((n) => n + 1)} />}

      {!data.editable && data.blocked_reason && (
        <section className="card border-slate-300 bg-slate-50">
          <h2 className="font-semibold text-ink">Rows are not added here by hand</h2>
          <p className="mt-1 text-sm text-slate-700">{data.blocked_reason}</p>
          {data.blocked_route && (
            <Link
              to={data.blocked_route}
              className="mt-2 inline-block text-sm font-medium text-civic-700 underline underline-offset-2"
            >
              Go to the right form →
            </Link>
          )}
        </section>
      )}

      <section>
        <h2 className="font-semibold text-ink">
          Real rows, from the running database
          {data.row_count > data.showing && (
            <span className="ml-2 text-sm font-normal text-slate-600">
              first {data.showing} of {data.row_count.toLocaleString()}
            </span>
          )}
        </h2>

        {data.rows.length === 0 ? (
          <p className="mt-2 text-slate-600">This table is empty.</p>
        ) : (
          <div className="mt-2 overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">Sample rows from {data.label}</caption>
              <thead>
                <tr className="table-head">
                  {data.columns.map((c) => (
                    <th key={c.name} scope="col" className="whitespace-nowrap py-2 pr-4">
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, i) => (
                  <tr key={i} className="border-b border-slate-200 align-top">
                    {row.map((cell, j) =>
                      data.columns[j].is_identifier && cell ? (
                        <td key={j} className="py-2 pr-4">
                          <CopyableId value={cell} />
                        </td>
                      ) : (
                        <td key={j} className="py-2 pr-4">
                          {cell ?? <span className="text-slate-400">—</span>}
                        </td>
                      ),
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

/**
 * An identifier, shown in full and copyable.
 *
 * It used to be cut to eight characters and greyed out, which looked tidier and destroyed the
 * only thing an identifier is for: telling two rows apart, or matching one against a row in
 * another table. Full value, readable contrast, and one click to copy it.
 */
function CopyableId({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      title="Copy this identifier"
      onClick={() => {
        navigator.clipboard?.writeText(value).then(
          () => {
            setCopied(true)
            setTimeout(() => setCopied(false), 1200)
          },
          () => undefined,
        )
      }}
      className="group inline-flex items-center gap-1.5 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-xs text-slate-700 transition-colors hover:border-civic-300 hover:bg-civic-50"
    >
      <span className="break-all text-left">{value}</span>
      <span aria-hidden className="shrink-0 text-slate-400 group-hover:text-civic-600">
        {copied ? '✓' : '⧉'}
      </span>
      <span className="sr-only">{copied ? 'Copied' : 'Copy'}</span>
    </button>
  )
}

/**
 * Add a row, for the reference tables where that is a real thing to do — another category of
 * problem, another police station, a different fine.
 *
 * Fields are built from the database's own columns, so an enum offers exactly the values the
 * column accepts and a map point asks for two numbers rather than for the WKT string whose axis
 * order is so easy to reverse. Anything the database fills in itself is not asked for at all.
 */
function CreateRow({ table, onCreated }: { table: TableDetail; onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<string | null>(null)

  function set(field: string, value: unknown) {
    setValues((prev) => ({ ...prev, [field]: value }))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await apiPost<{ id: string }>(`/api/schema/tables/${table.name}`, values)
      setCreated(result.id)
      setValues({})
      onCreated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That row could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <section className="card flex flex-wrap items-center justify-between gap-3 border-civic-200 bg-civic-50/50">
        <div>
          <h2 className="font-semibold text-ink">Add your own</h2>
          <p className="text-sm text-slate-700">
            This is reference data, so you can add to it here. Whatever you add is live
            immediately — the rest of the app will use it.
          </p>
        </div>
        <button type="button" className="btn-primary shrink-0" onClick={() => setOpen(true)}>
          Add a row
        </button>
      </section>
    )
  }

  return (
    <section className="card border-civic-200">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-ink">Add to {table.label}</h2>
        <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>

      {created && (
        <p role="status" className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
          Saved. It is in the database now and the rest of the app can already use it.
          <span className="mt-1 block font-mono text-xs">{created}</span>
        </p>
      )}
      {error && (
        <p className="mt-3">
          <ErrorNote message={error} />
        </p>
      )}

      <form onSubmit={submit} className="mt-4 grid gap-4 sm:grid-cols-2">
        {table.fields.map((f) => (
          <Field key={f.name} field={f} value={values[f.name]} onChange={(v) => set(f.name, v)} />
        ))}
        <div className="sm:col-span-2">
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Saving…' : `Add to ${table.label}`}
          </button>
        </div>
      </form>
    </section>
  )
}

function Field({
  field,
  value,
  onChange,
}: {
  field: FormField
  value: unknown
  onChange: (v: unknown) => void
}) {
  const id = `f-${field.name}`
  const label = (
    <label className="field-label" htmlFor={id}>
      {field.label}
      {!field.required && <span className="font-normal text-slate-500"> (optional)</span>}
    </label>
  )
  const help = field.help && <p className="mt-1 text-xs text-slate-600">{field.help}</p>

  if (field.kind === 'latlng') {
    const v = (value ?? {}) as { lat?: string; lng?: string }
    return (
      <div className="sm:col-span-2">
        {label}
        <div className="flex flex-wrap gap-2">
          <input
            id={id}
            className="field-input max-w-[12rem]"
            placeholder="Latitude, e.g. 12.9855"
            value={v.lat ?? ''}
            onChange={(e) => onChange({ ...v, lat: e.target.value })}
          />
          <input
            className="field-input max-w-[12rem]"
            placeholder="Longitude, e.g. 77.5955"
            value={v.lng ?? ''}
            onChange={(e) => onChange({ ...v, lng: e.target.value })}
          />
        </div>
        <p className="mt-1 text-xs text-slate-600">
          Two numbers, not a map string — that way the latitude and longitude cannot end up the
          wrong way round.
        </p>
      </div>
    )
  }

  if (field.kind === 'bbox') {
    const v = (value ?? {}) as Record<string, string>
    return (
      <div className="sm:col-span-2">
        {label}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(['lat1', 'lng1', 'lat2', 'lng2'] as const).map((k) => (
            <input
              key={k}
              className="field-input"
              placeholder={k}
              value={v[k] ?? ''}
              onChange={(e) => onChange({ ...v, [k]: e.target.value })}
            />
          ))}
        </div>
        <p className="mt-1 text-xs text-slate-600">
          Two opposite corners of the area, as latitude and longitude.
        </p>
      </div>
    )
  }

  if (field.kind === 'enum') {
    return (
      <div>
        {label}
        <select
          id={id}
          className="field-input"
          value={(value as string) ?? ''}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">—</option>
          {field.options.map((o) => (
            <option key={o} value={o}>
              {o.replace(/_/g, ' ').toLowerCase()}
            </option>
          ))}
        </select>
        {help}
      </div>
    )
  }

  if (field.kind === 'boolean') {
    return (
      <div>
        {label}
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            id={id}
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(e.target.checked)}
          />
          Yes
        </label>
        {help}
      </div>
    )
  }

  if (field.kind === 'longtext') {
    return (
      <div className="sm:col-span-2">
        {label}
        <textarea
          id={id}
          rows={3}
          className="field-input"
          value={(value as string) ?? ''}
          onChange={(e) => onChange(e.target.value)}
        />
        {help}
      </div>
    )
  }

  return (
    <div>
      {label}
      <input
        id={id}
        type={field.kind === 'number' ? 'number' : field.kind === 'date' ? 'date' : 'text'}
        step={field.kind === 'number' ? 'any' : undefined}
        maxLength={field.max_length ?? undefined}
        className="field-input"
        value={(value as string) ?? ''}
        onChange={(e) => onChange(e.target.value)}
      />
      {help}
    </div>
  )
}
