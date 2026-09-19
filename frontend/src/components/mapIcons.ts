import L from 'leaflet'

import type { IssueStatus } from '../lib/api'

const STATUS_COLORS: Record<IssueStatus, string> = {
  reported: '#475569',
  acknowledged: '#0284c7',
  in_progress: '#d97706',
  resolved: '#059669',
  overdue: '#dc2626',
}

/**
 * Inline divIcons rather than Leaflet's default PNG marker: the default icon resolves its image
 * via a bundler-relative URL that breaks under Vite, and this avoids shipping marker assets at
 * all - which also keeps the payload down on a 3G connection.
 */
export function statusMarker(status: IssueStatus): L.DivIcon {
  const color = STATUS_COLORS[status]
  return L.divIcon({
    className: '',
    html: `<span style="display:block;width:18px;height:18px;border-radius:9999px;background:${color};border:3px solid white;box-shadow:0 0 0 1px rgba(0,0,0,.35)"></span>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  })
}

export const pinMarker: L.DivIcon = L.divIcon({
  className: '',
  html: `<span style="display:block;width:22px;height:22px;border-radius:9999px;background:#166058;border:4px solid white;box-shadow:0 0 0 1px rgba(0,0,0,.4)"></span>`,
  iconSize: [22, 22],
  iconAnchor: [11, 11],
})

// Fictional "Demo City" centre, matching the seeded ward grid.
export const DEMO_CITY_CENTER: [number, number] = [12.99, 77.6]
