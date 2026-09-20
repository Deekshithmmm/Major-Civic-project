import type { MediaKind } from '../lib/api'

/**
 * A report's photo or video. Videos are stored as browser-playable MP4/WebM with their audio
 * track removed, so they are muted by nature - `controls` is still shown because a citizen or
 * officer needs to scrub through a clip to see the problem.
 */
export default function ReportMedia({
  mediaId,
  kind,
  label,
  className = '',
}: {
  mediaId: string
  kind: MediaKind | null
  label: string
  className?: string
}) {
  const src = `/api/media/${mediaId}`

  if (kind === 'video') {
    return (
      <video
        src={src}
        controls
        playsInline
        preload="metadata"
        aria-label={label}
        className={`rounded-md border border-slate-200 bg-black ${className}`}
      />
    )
  }

  return <img src={src} alt={label} className={`rounded-md border border-slate-200 ${className}`} />
}
