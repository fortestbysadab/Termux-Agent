/**
 * Real brand marks for the connector catalogue.
 *
 * Sourced from `simple-icons` (CC0) and bundled locally — no CDN, no runtime
 * fetch, so the console still works offline on the phone. Each mark keeps its
 * brand colour (that is the point of a logo); the surrounding card supplies the
 * theme-aware surface.
 */
import {
  siGithub,
  siGoogledrive,
  siGoogledocs,
  siNotion,
  siGmail,
  siLinear,
  siGooglecalendar,
  siGoogleslides,
  siGooglesheets,
  siDropbox,
  siVercel,
  siSupabase,
} from 'simple-icons';

const BY_ID = {
  github: siGithub,
  drive: siGoogledrive,
  docs: siGoogledocs,
  notion: siNotion,
  gmail: siGmail,
  linear: siLinear,
  calendar: siGooglecalendar,
  slides: siGoogleslides,
  sheets: siGooglesheets,
  dropbox: siDropbox,
  vercel: siVercel,
  supabase: siSupabase,
};

export function brandIcon(id) {
  return BY_ID[id] || null;
}

/** Perceptual luminance of a #rrggbb string, 0 (black) → 1 (white). */
function luminance(hex) {
  const n = parseInt(hex, 16);
  const chan = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * chan[0] + 0.7152 * chan[1] + 0.0722 * chan[2];
}

/** Renders the brand glyph, or a neutral plug for custom MCP servers. */
export function BrandMark({ id, size = 26, muted = false }) {
  const icon = brandIcon(id);
  const hex = icon?.hex || '6b7280';
  // Marks whose brand colour is near-black (GitHub, Notion, Vercel) would vanish
  // on a dark tile, so they inherit the theme's foreground instead — the same
  // call GitHub itself makes with its monochrome logo.
  const color = muted || luminance(hex) < 0.12 ? 'currentColor' : `#${hex}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      role="img"
      aria-label={icon ? `${icon.title} logo` : 'Connector'}
      focusable="false"
      style={{ display: 'block', color }}
    >
      {icon ? (
        <path d={icon.path} fill="currentColor" />
      ) : (
        <path
          d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-6 6 6 6 0 0 1-6-6V8ZM12 17v4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  );
}
