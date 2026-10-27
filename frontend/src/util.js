import { useEffect, useState } from 'react';

export function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const k = 1024;
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(k)));
  return `${parseFloat((bytes / k ** i).toFixed(1))} ${units[i]}`;
}

export function formatTime(ts) {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function fileExt(name = '') {
  const parts = name.split('.');
  return (parts.length > 1 ? parts.pop() : 'file').toUpperCase().slice(0, 5);
}

export function extensionOf(name = '') {
  const i = name.lastIndexOf('.');
  return i === -1 ? '' : name.slice(i).toLowerCase();
}

export function timeAgo(ts) {
  if (!ts) return '';
  const secs = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (secs < 60) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

/* ------------------------------------------------------------------ media */

export function useMediaQuery(query) {
  const [matches, setMatches] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches,
  );
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);
  return matches;
}

export const useReducedMotion = () => useMediaQuery('(prefers-reduced-motion: reduce)');

/** Resolves the stored preference ('system' | 'light' | 'dark') to a concrete theme. */
export function useResolvedTheme(preference) {
  const systemDark = useMediaQuery('(prefers-color-scheme: dark)');
  if (preference === 'light' || preference === 'dark') return preference;
  return systemDark ? 'dark' : 'light';
}

/* --------------------------------------------------------------- markdown */

const INLINE = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;

function inline(text, keyPrefix) {
  const out = [];
  let last = 0;
  let match;
  let i = 0;
  INLINE.lastIndex = 0;
  while ((match = INLINE.exec(text)) !== null) {
    if (match.index > last) out.push(text.slice(last, match.index));
    const token = match[0];
    const key = `${keyPrefix}-i${i}`;
    i += 1;
    if (token.startsWith('**')) out.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    else if (token.startsWith('`')) out.push(<code key={key}>{token.slice(1, -1)}</code>);
    else if (token.startsWith('[')) {
      const m = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      out.push(
        <a key={key} href={m[2]} target="_blank" rel="noopener noreferrer">
          {m[1]}
        </a>,
      );
    } else out.push(<em key={key}>{token.slice(1, -1)}</em>);
    last = match.index + token.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/**
 * Small, dependency-free markdown renderer that returns React nodes
 * (never innerHTML), so model output can never inject markup.
 */
export function renderMarkdown(source) {
  if (!source) return null;
  const blocks = String(source).split(/\n{2,}/);
  const nodes = [];

  blocks.forEach((raw, bi) => {
    let block = raw.trim();
    if (!block) return;

    const fence = /^```[a-zA-Z0-9_-]*\n?([\s\S]*?)```$/.exec(block);
    if (fence) {
      nodes.push(
        <pre key={`b${bi}`} className="md-pre">
          <code>{fence[1].replace(/\n$/, '')}</code>
        </pre>,
      );
      return;
    }

    const heading = /^(#{1,4})\s+(.*)$/.exec(block);
    if (heading) {
      const level = heading[1].length;
      const Tag = `h${Math.min(4, level + 2)}`;
      nodes.push(<Tag key={`b${bi}`} className="md-heading">{inline(heading[2], `b${bi}`)}</Tag>);
      return;
    }

    // Pipe tables (models emit these constantly)
    const lines = block.split('\n');
    if (
      lines.length >= 2 &&
      lines[0].includes('|') &&
      /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[1]) &&
      lines[1].includes('-')
    ) {
      const cells = (row) =>
        row
          .replace(/^\s*\|/, '')
          .replace(/\|\s*$/, '')
          .split('|')
          .map((c) => c.trim());
      const head = cells(lines[0]);
      const body = lines.slice(2).filter((l) => l.includes('|')).map(cells);
      nodes.push(
        <div className="md-table-wrap" key={`b${bi}`}>
          <table className="md-table">
            <thead>
              <tr>
                {head.map((h, hi) => (
                  <th key={hi}>{inline(h, `b${bi}-h${hi}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((row, ri) => (
                <tr key={ri}>
                  {head.map((_, ci) => (
                    <td key={ci}>{inline(row[ci] ?? '', `b${bi}-${ri}-${ci}`)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      return;
    }

    // Bullet / numbered lists
    if (lines.every((l) => /^\s*[-*+]\s+/.test(l))) {
      nodes.push(
        <ul key={`b${bi}`} className="md-list">
          {lines.map((l, li) => (
            <li key={li}>{inline(l.replace(/^\s*[-*+]\s+/, ''), `b${bi}-${li}`)}</li>
          ))}
        </ul>,
      );
      return;
    }
    if (lines.every((l) => /^\s*\d+[.)]\s+/.test(l))) {
      nodes.push(
        <ol key={`b${bi}`} className="md-list">
          {lines.map((l, li) => (
            <li key={li}>{inline(l.replace(/^\s*\d+[.)]\s+/, ''), `b${bi}-${li}`)}</li>
          ))}
        </ol>,
      );
      return;
    }

    if (/^&gt;\s|^>\s/.test(block)) {
      nodes.push(
        <blockquote key={`b${bi}`} className="md-quote">
          {inline(block.replace(/^(&gt;|>)\s?/gm, ''), `b${bi}`)}
        </blockquote>,
      );
      return;
    }

    nodes.push(
      <p key={`b${bi}`}>
        {inline(block.replace(/\n/g, '\n'), `b${bi}`).map((chunk, ci) =>
          typeof chunk === 'string'
            ? chunk.split('\n').map((seg, si, arr) => (
                <span key={`${ci}-${si}`}>
                  {seg}
                  {si < arr.length - 1 ? <br /> : null}
                </span>
              ))
            : chunk,
        )}
      </p>,
    );
  });

  return nodes;
}
