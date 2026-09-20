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
