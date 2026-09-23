const TOKEN_KEY = 'civic_officer_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export type ApiErrorKind = 'http' | 'network' | 'timeout'

export class ApiError extends Error {
  status: number
  kind: ApiErrorKind
  constructor(status: number, message: string, kind: ApiErrorKind = 'http') {
    super(message)
    this.status = status
    this.kind = kind
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: authHeaders() })
  return handle<T>(res)
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return handle<T>(res)
}

/**
 * Multipart upload with real progress events. Uses XMLHttpRequest because fetch() still has no
 * upload-progress API - the spec requires showing real progress on a 3G connection, and a fake
 * indeterminate spinner is not that.
 *
 * `processingTimeoutMs` only starts once the upload has finished. A slow 3G upload must never be
 * cut off, but a server that takes the file and then never answers must not leave the form stuck
 * on "100%" forever either.
 */
export function apiUpload<T>(
  path: string,
  form: FormData,
  onProgress?: (percent: number) => void,
  processingTimeoutMs = 2 * 60_000,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    let processingTimer: number | undefined
    xhr.open('POST', path)

    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    })

    xhr.upload.addEventListener('load', () => {
      onProgress?.(100)
      processingTimer = window.setTimeout(() => {
        reject(new ApiError(0, 'Server did not respond after upload', 'timeout'))
        xhr.abort()
      }, processingTimeoutMs)
    })

    xhr.addEventListener('loadend', () => window.clearTimeout(processingTimer))
    xhr.addEventListener('abort', () => reject(new ApiError(0, 'Upload aborted', 'network')))

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T)
        } catch {
          reject(new ApiError(xhr.status, 'Malformed response'))
        }
      } else {
        let detail = xhr.statusText
        try {
          const body = JSON.parse(xhr.responseText)
          if (typeof body?.detail === 'string') detail = body.detail
        } catch {
          /* non-JSON error body */
        }
        reject(new ApiError(xhr.status, detail))
      }
    })

    xhr.addEventListener('error', () => reject(new ApiError(0, 'Network error', 'network')))
    xhr.send(form)
  })
}

/**
 * Client-side compression before upload (spec 2.6: "Compress client-side before upload"). A
 * 12MP phone photo is ~4MB; this gets it to a few hundred KB, which is the difference between a
 * report that submits on 3G and one that times out. Videos are passed through untouched -
 * in-browser video transcoding is not worth the payload on a low-end device.
 */
export async function compressImage(file: File, maxDimension = 1600, quality = 0.75): Promise<File> {
  if (!file.type.startsWith('image/')) return file

  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height))
  if (scale === 1 && file.size < 400_000) return file

  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)

  const ctx = canvas.getContext('2d')
  if (!ctx) return file
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/jpeg', quality),
  )
  if (!blob || blob.size >= file.size) return file

  return new File([blob], file.name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg' })
}

// --- Module 3 types ---------------------------------------------------------

export type IssueStatus = 'reported' | 'acknowledged' | 'in_progress' | 'resolved' | 'overdue'

export type MediaKind = 'image' | 'video'

export type IssueCategory = {
  id: string
  slug: string
  label: string
  sla_hours: number
  escalation_department: string
  escalation_department_tier2: string | null
}

export type Issue = {
  id: string
  category_slug: string
  category_label: string
  description: string | null
  lat: number
  lng: number
  status: IssueStatus
  upvote_count: number
  sla_deadline: string
  created_at: string
  media_id: string | null
  media_kind: MediaKind | null
  tracking_token: string
}

export type IssueDetail = Issue & {
  history: { status: IssueStatus; note: string | null; created_at: string }[]
  resolution_proof_media_id: string | null
}

export type IssueCreateResult = {
  id: string
  tracking_token: string
  status: IssueStatus
  sla_deadline: string
  merged_into_existing: boolean
}

export type ShareableCard = {
  issue_id: string
  share_text: string
  share_url: string
}

export type CurrentUser = {
  id: string
  email: string
  full_name: string
  role: string
  department: string | null
}

// --- Module 2 types ---------------------------------------------------------

export type AccusedPartyType =
  | 'state_govt_employee'
  | 'central_govt_employee'
  | 'police_personnel'
  | 'municipal_or_dept_staff'

export type PublicStatusBadge =
  | 'unverified_allegation'
  | 'under_investigation'
  | 'action_taken'
  | 'dismissed'

export type ModerationStatus = 'pending' | 'approved' | 'rejected'

export type RoutingRule = {
  accused_party_type: AccusedPartyType
  primary_route_body: string
  notify_local_police: boolean
}

export type PublishedReply = {
  id: string
  body: string
  author_department: string
  author_designation: string
  published_at: string | null
}

export type FeedItem = {
  id: string
  accused_department: string
  accused_designation: string
  description: string | null
  geohash: string
  public_status_badge: PublicStatusBadge
  created_at: string
  media_id: string
  media_kind: MediaKind
  replies: PublishedReply[]
}

export type CorruptionReportResult = {
  tracking_token: string
  moderation_status: ModerationStatus
}

export type CorruptionReportStatus = {
  tracking_token: string
  moderation_status: ModerationStatus
  public_status_badge: PublicStatusBadge
  created_at: string
  taken_down: boolean
  takedown_reason: string | null
}

// --- Grievance channel and right of reply (IT Rules 2021) -------------------

export type GrievanceGround =
  | 'factually_incorrect'
  | 'identifies_private_person'
  | 'defamatory'
  | 'sub_judice'
  | 'not_my_department'
  | 'other'

export type GrievanceStatus = 'received' | 'acknowledged' | 'upheld' | 'rejected'

export type GrievanceOfficer = {
  name: string
  designation: string
  email: string
  address: string
  acknowledgement_deadline_hours: number
  resolution_deadline_days: number
}

export type GrievanceResult = {
  ticket: string
  status: GrievanceStatus
  acknowledged: boolean
  resolution_due_by: string
}

export type GrievanceTicket = {
  ticket: string
  status: GrievanceStatus
  ground: GrievanceGround
  received_at: string
  acknowledged_at: string | null
  resolution_due_by: string
  resolved_at: string | null
  resolution_note: string | null
  overdue: boolean
}

export type GrievanceQueueItem = {
  id: string
  ticket: string
  report_id: string
  ground: GrievanceGround
  body: string
  complainant_name: string
  complainant_email: string
  complainant_designation: string | null
  status: GrievanceStatus
  received_at: string
  acknowledged_at: string | null
  resolution_due_by: string
  overdue: boolean
  report_department: string
  report_designation: string
  report_taken_down: boolean
}

export type ReplyStatus = 'pending' | 'published' | 'rejected'

export type ReplyQueueItem = {
  id: string
  report_id: string
  body: string
  author_department: string
  author_designation: string
  author_name: string
  author_contact_email: string
  status: ReplyStatus
  submitted_at: string
  report_department: string
  report_designation: string
}

export type GrievanceCompliance = {
  grievances_received: number
  acknowledged_within_deadline: number
  acknowledgement_deadline_missed: number
  resolved_within_deadline: number
  resolution_deadline_missed: number
  open_past_deadline: number
  upheld: number
  rejected: number
  on_time_resolution_rate: number | null
  acknowledgement_deadline_hours: number
  resolution_deadline_days: number
}

// --- Module 1 types ---------------------------------------------------------

export type IdentityPath = 'anpr' | 'unidentified'

export type ViolationCaseStatus = 'pending_review' | 'confirmed' | 'reclassified' | 'dismissed'

export type ViolationClass = {
  id: string
  slug: string
  label: string
  identity_path: IdentityPath
  statutory_section: string | null
}

export type ViolationCase = {
  id: string
  violation_class_slug: string
  violation_class_label: string
  confidence_score: number | null
  lat: number
  lng: number
  media_id: string
  media_kind: MediaKind
  identity_path: IdentityPath
  resolved_plate_number: string | null
  status: ViolationCaseStatus
  source: string
  created_at: string
}

export type Challan = {
  id: string
  case_id: string
  statutory_section: string | null
  amount_rupees: number
  due_date: string
  status: string
}

// --- Police station types ---------------------------------------------------

export type StationDirectoryEntry = {
  id: string
  name: string
  code: string
  address: string | null
  lat: number | null
  lng: number | null
  contact_phone: string | null
  sho_name: string | null
  ward_name: string | null
  distance_km: number | null
}

export type StationDetail = StationDirectoryEntry & {
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

export type StationSummary = {
  id: string
  name: string
  code: string
  address: string | null
  sho_name: string | null
}

export type DiaryEntry = {
  id: string
  entry_date: string
  serial_no: number
  entry_type: string
  detail: string
  report_id: string | null
  fir_id: string | null
  officer_user_id: string | null
  created_at: string
}

export type StationReportRow = {
  id: string
  category: string
  geohash: string
  is_restricted: boolean
  has_evidence: boolean
  acknowledged_at: string | null
  closed_at: string | null
  closed_without_fir_reason: string | null
  created_at: string
  fir_id: string | null
  fir_number: string | null
  hours_since_report: number
  overdue_for_acknowledgement: boolean
  overdue_for_fir: boolean
}

export type FirRecord = {
  id: string
  fir_number: string
  year: number
  station_id: string
  station_name: string | null
  report_id: string
  category: string | null
  sections: string
  is_zero_fir: boolean
  transferred_to_station_id: string | null
  investigating_officer_id: string | null
  registered_at: string
  investigation_deadline: string
  status: string
  chargesheet_filed_at: string | null
  court_name: string | null
  closure_reason: string | null
  closed_at: string | null
  days_remaining: number
}

export type CaseDiaryEntry = {
  id: string
  officer_user_id: string
  detail: string
  created_at: string
}

// --- The database view (development only) -----------------------------------

export type TableSummary = {
  name: string
  label: string
  row_is: string
  row_count: number
  append_only: boolean
  has_masked: boolean
}

export type TableGroup = {
  key: string
  label: string
  blurb: string
  tables: TableSummary[]
}

export type SchemaOverview = {
  groups: TableGroup[]
  table_count: number
  undocumented: string[]
}

export type TableColumn = {
  name: string
  label: string
  means: string | null
  type: string
  optional: boolean
  points_at: string | null
  is_identifier: boolean
}

export type TableDetail = {
  name: string
  label: string
  row_is: string
  purpose: string
  note: string | null
  append_only: boolean
  row_count: number
  showing: number
  columns: TableColumn[]
  rows: (string | null)[][]
  withheld: { column: string; reason: string }[]
}
