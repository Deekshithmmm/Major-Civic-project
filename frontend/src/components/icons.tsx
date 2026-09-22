/**
 * Inline SVG icons. Hand-written rather than pulled from an icon package: there are a dozen of
 * them, and a dependency would ship thousands to a page that must load on a low-end phone.
 *
 * All are decorative and marked aria-hidden - every place one appears already has a text label,
 * so announcing the icon as well would just repeat it.
 */

type IconProps = { className?: string }

function Svg({ className = 'h-5 w-5', children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {children}
    </svg>
  )
}

/** Civic infrastructure: a road running to the horizon. */
export function IconRoad({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4 21 8 3M20 21 16 3" />
      <path d="M12 4v3M12 11v3M12 18v3" />
    </Svg>
  )
}

/** Corruption: a note passing hand to hand. */
export function IconBribe({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="2.5" y="6" width="19" height="10" rx="2" />
      <circle cx="12" cy="11" r="2.5" />
      <path d="M6 11h.01M18 11h.01" />
      <path d="M5 20h14" />
    </Svg>
  )
}

/** Violations: evidence from a camera. */
export function IconCamera({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M3 8h3l1.5-2h9L18 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z" />
      <circle cx="12" cy="13" r="3.5" />
    </Svg>
  )
}

/** Emergency: a siren. */
export function IconSiren({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M7 18v-5a5 5 0 0 1 10 0v5" />
      <path d="M4 18h16v3H4z" />
      <path d="M12 3v2M4.5 7 6 8M19.5 7 18 8" />
    </Svg>
  )
}

/** Police station. */
export function IconStation({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4 21V9l8-5 8 5v12" />
      <path d="M9 21v-6h6v6" />
      <path d="M12 8.5 13 10h-2l1-1.5Z" />
    </Svg>
  )
}

/** Accountability: a ledger of bars. */
export function IconLedger({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M3 21h18" />
      <rect x="5" y="11" width="3.5" height="7" rx="1" />
      <rect x="10.25" y="7" width="3.5" height="11" rx="1" />
      <rect x="15.5" y="14" width="3.5" height="4" rx="1" />
    </Svg>
  )
}

export function IconShield({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 3 5 6v5.5c0 4.3 2.9 7.6 7 9.5 4.1-1.9 7-5.2 7-9.5V6l-7-3Z" />
      <path d="m9.5 12 1.8 1.8 3.5-3.6" />
    </Svg>
  )
}

export function IconClock({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 1.8" />
    </Svg>
  )
}

export function IconAlert({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 4.5 2.8 20h18.4L12 4.5Z" />
      <path d="M12 10v4M12 17h.01" />
    </Svg>
  )
}

export function IconArrowRight({ className = 'h-4 w-4' }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4 12h15M13 6l6 6-6 6" />
    </Svg>
  )
}
