/**
 * Inline icon set.
 *
 * A hand-picked subset drawn on a 24×24 grid with a 1.6 stroke, rendered with
 * `currentColor` so every icon follows the theme and the surrounding text
 * colour. Kept inline rather than pulled from a library: it is a few hundred
 * bytes, and it means no icon font or CDN request.
 */

const PATHS = {
  // -- navigation
  dashboard: (
    <>
      <rect x="3" y="3" width="7.5" height="8.5" rx="1.6" />
      <rect x="13.5" y="3" width="7.5" height="5.5" rx="1.6" />
      <rect x="3" y="15" width="7.5" height="6" rx="1.6" />
      <rect x="13.5" y="12" width="7.5" height="9" rx="1.6" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14M5 12h14" />
    </>
  ),
  history: (
    <>
      <path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1" />
      <path d="M3 4v4h4" />
      <path d="M12 7.5V12l3 1.8" />
    </>
  ),
  memory: (
    <>
      <path d="M12 4.2a3 3 0 0 0-3 3v.3a2.6 2.6 0 0 0-1.7 4.4A2.8 2.8 0 0 0 8.6 17a2.7 2.7 0 0 0 3.4 2.5V4.2Z" />
      <path d="M12 4.2a3 3 0 0 1 3 3v.3a2.6 2.6 0 0 1 1.7 4.4A2.8 2.8 0 0 1 15.4 17a2.7 2.7 0 0 1-3.4 2.5" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="2.9" />
      <path d="M19.1 14.4a1.5 1.5 0 0 0 .3 1.6l.1.1a1.8 1.8 0 1 1-2.5 2.5l-.1-.1a1.5 1.5 0 0 0-2.5 1v.2a1.8 1.8 0 1 1-3.6 0v-.1a1.5 1.5 0 0 0-2.6-1l-.1.1a1.8 1.8 0 1 1-2.5-2.5l.1-.1a1.5 1.5 0 0 0-1-2.5H4.6a1.8 1.8 0 0 1 0-3.6h.1a1.5 1.5 0 0 0 1-2.6l-.1-.1a1.8 1.8 0 0 1 2.5-2.5l.1.1a1.5 1.5 0 0 0 1.6.3h.1a1.5 1.5 0 0 0 .9-1.4V4.6a1.8 1.8 0 1 1 3.6 0v.1a1.5 1.5 0 0 0 2.5 1l.1-.1a1.8 1.8 0 0 1 2.5 2.5l-.1.1a1.5 1.5 0 0 0 1 2.5h.2a1.8 1.8 0 0 1 0 3.6h-.1a1.5 1.5 0 0 0-1.4.9Z" />
    </>
  ),

  // -- agents
  chart: (
    <>
      <path d="M4 19V5" />
      <path d="M4 19h16" />
      <path d="M7.5 15.5l3.5-4.5 3 2.5 4.5-6" />
    </>
  ),
  chat: (
    <>
      <path d="M20 12.5a7.5 7.5 0 0 1-10.9 6.7L4 20.5l1.4-4.6A7.5 7.5 0 1 1 20 12.5Z" />
      <path d="M9 11.5h6M9 14.5h3.5" />
    </>
  ),
  news: (
    <>
      <path d="M4.5 5.5h11a1 1 0 0 1 1 1v11a2 2 0 0 0 2 2H6a1.5 1.5 0 0 1-1.5-1.5Z" />
      <path d="M16.5 9.5H19a1 1 0 0 1 1 1v7a2 2 0 0 1-2 2" />
      <path d="M7.5 9h5M7.5 12h5M7.5 15h3" />
    </>
  ),
  ledger: (
    <>
      <path d="M5 4.5h11.5a1.5 1.5 0 0 1 1.5 1.5v13.5H6.5A1.5 1.5 0 0 1 5 18Z" />
      <path d="M5 16.5h13" />
      <path d="M9 8h5M9 11h5" />
    </>
  ),
  trendUp: (
    <>
      <path d="M3.5 16.5 9 11l3.5 3L20.5 6" />
      <path d="M15.5 6h5v5" />
    </>
  ),
  trendDown: (
    <>
      <path d="M3.5 7.5 9 13l3.5-3 8 8.5" />
      <path d="M15.5 18.5h5v-5" />
    </>
  ),
  gavel: (
    <>
      <path d="m13.5 6.5 4 4" />
      <rect x="9.2" y="4.6" width="8.4" height="4.6" rx="1.2" transform="rotate(-45 9.2 4.6)" />
      <path d="m11.5 10.5-6 6" />
      <path d="M4 20h7" />
    </>
  ),
  briefcase: (
    <>
      <rect x="3" y="7.5" width="18" height="12" rx="2" />
      <path d="M9 7.5V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1.5" />
      <path d="M3 12.5h18" />
    </>
  ),
  flame: (
    <>
      <path d="M12 3.5s4.5 3.6 4.5 8a4.5 4.5 0 0 1-9 0c0-1.6.7-2.9 1.5-3.9 0 1.6.8 2.4 1.6 2.4.9 0 1.4-.8 1.4-2.4 0-1.7-.5-3-1-4.1Z" />
      <path d="M12 20.5a6 6 0 0 0 6-6" />
      <path d="M12 20.5a6 6 0 0 1-6-6" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3.5 5 6v5.5c0 4.2 2.9 7.6 7 9 4.1-1.4 7-4.8 7-9V6Z" />
      <path d="m9.2 12 2 2 3.6-3.8" />
    </>
  ),
  scale: (
    <>
      <path d="M12 4v16M7 20h10" />
      <path d="M5.5 7.5 12 6l6.5 1.5" />
      <path d="M5.5 7.5 3 13a2.6 2.6 0 0 0 5 0Z" />
      <path d="M18.5 7.5 16 13a2.6 2.6 0 0 0 5 0Z" />
    </>
  ),
  verdict: (
    <>
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
      <path d="M9.5 8h5" />
    </>
  ),

  // -- state
  check: <path d="m4.5 12.5 5 5 10-11" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  chevronRight: <path d="m9 5 7 7-7 7" />,
  chevronDown: <path d="m5 9 7 7 7-7" />,
  chevronUp: <path d="m5 15 7-7 7 7" />,
  arrowRight: (
    <>
      <path d="M4 12h15" />
      <path d="m13 6 6 6-6 6" />
    </>
  ),
  arrowLeft: (
    <>
      <path d="M20 12H5" />
      <path d="m11 6-6 6 6 6" />
    </>
  ),
  play: <path d="M7 4.8v14.4l12-7.2Z" />,
  stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
  download: (
    <>
      <path d="M12 3.5v12" />
      <path d="m7.5 11 4.5 4.5 4.5-4.5" />
      <path d="M4.5 19.5h15" />
    </>
  ),
  trash: (
    <>
      <path d="M4.5 7h15" />
      <path d="M9 7V5.2A1.2 1.2 0 0 1 10.2 4h3.6A1.2 1.2 0 0 1 15 5.2V7" />
      <path d="M6.5 7.5 7.4 19a1.6 1.6 0 0 0 1.6 1.5h6a1.6 1.6 0 0 0 1.6-1.5l.9-11.5" />
      <path d="M10.5 11v6M13.5 11v6" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4.5 4.5" />
    </>
  ),
  alert: (
    <>
      <path d="M12 4.5 2.9 20h18.2Z" />
      <path d="M12 10v4.2M12 17.3v.2" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5M12 8.2v.2" />
    </>
  ),
  key: (
    <>
      <circle cx="8" cy="12" r="3.5" />
      <path d="M11.5 12H20" />
      <path d="M17 12v3M20 12v2.5" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.2 5.2l1.4 1.4M17.4 17.4l1.4 1.4M18.8 5.2l-1.4 1.4M6.6 17.4l-1.4 1.4" />
    </>
  ),
  moon: <path d="M20 14.2A8.2 8.2 0 0 1 9.8 4a8.5 8.5 0 1 0 10.2 10.2Z" />,
  spark: (
    <>
      <path d="M12 3.5 13.6 9 19 10.5 13.6 12 12 17.5 10.4 12 5 10.5 10.4 9Z" />
      <path d="M18.5 16.5 19 18.5l2 .5-2 .5-.5 2-.5-2-2-.5 2-.5Z" />
    </>
  ),
  cpu: (
    <>
      <rect x="6.5" y="6.5" width="11" height="11" rx="2" />
      <rect x="10" y="10" width="4" height="4" rx="1" />
      <path d="M10 3v3.5M14 3v3.5M10 17.5V21M14 17.5V21M3 10h3.5M3 14h3.5M17.5 10H21M17.5 14H21" />
    </>
  ),
  tool: (
    <>
      <path d="M14.5 6.5a4 4 0 0 0 5.2 5.2l-8 8a2.6 2.6 0 0 1-3.7-3.7Z" />
      <path d="M14.5 6.5 17 4" />
    </>
  ),
  activity: <path d="M3 12.5h4l2.5-7 4 14 2.5-7H21" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 1.8" />
    </>
  ),
  target: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="0.6" fill="currentColor" />
    </>
  ),
  layers: (
    <>
      <path d="m12 3.5 8.5 4.5-8.5 4.5L3.5 8Z" />
      <path d="m3.5 12.5 8.5 4.5 8.5-4.5" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 11.5A8 8 0 0 0 6.3 6.3L3.5 9" />
      <path d="M4 12.5a8 8 0 0 0 13.7 5.2l2.8-2.7" />
      <path d="M3.5 4.5V9H8M20.5 19.5V15H16" />
    </>
  ),
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  logo: (
    <>
      <path d="M4 18.5V9.2a1 1 0 0 1 1.7-.7l3.1 3.1a1 1 0 0 0 1.5 0l3.4-4a1 1 0 0 1 1.6.1L20 13" />
      <circle cx="19.6" cy="6.4" r="1.9" />
      <path d="M4 20.5h16" />
    </>
  ),
};

export default function Icon({ name, size = 16, className = '', strokeWidth = 1.6, ...rest }) {
  const path = PATHS[name];
  if (!path) return null;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {path}
    </svg>
  );
}
