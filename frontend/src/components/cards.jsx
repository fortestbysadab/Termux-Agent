import { useState } from 'react';
import { formatBytes, fileExt } from '../util.js';
import { CopyChip, Icon, Badge } from './ui.jsx';
import { OrbSwap } from './AgentAvatar.jsx';

/* --------------------------------------------------------------- tool runs */

/**
 * One executed tool: a terminal command or an MCP connector call.
 * Collapsed by default, expands to the full stdout/stderr or JSON payload.
 */
export function ToolRunCard({ run, theme, reduced, index = 0 }) {
  // History rows arrive as {name, detail:{...}}; live rows are already flat.
  const r = run.detail ? { ...run.detail } : run;
  const isTerminal = r.tool === 'terminal';
  const ok = r.ok !== false;
  const running = r.state === 'running';
  const [open, setOpen] = useState(false);

  const title = isTerminal ? r.command : r.tool || r.name || run.name || 'tool';
  const output = isTerminal
    ? `${r.stdout || ''}${r.stderr ? `\n${r.stderr}` : ''}`.trim()
    : JSON.stringify(r.result ?? {}, null, 2);

  return (
    <div
      className={`tool-card ${ok ? '' : 'is-error'} ${running ? 'is-running' : ''}`}
      style={{ '--i': index }}
    >
      <button
        type="button"
        className="tool-head"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className={`tool-kind ${isTerminal ? 'terminal' : 'mcp'}`}>
          {isTerminal ? <Icon.Terminal size={13} /> : <Icon.Plug size={13} />}
          {isTerminal ? 'bash' : 'mcp'}
        </span>

        {running ? (
          <span className="tool-running">
            <OrbSwap state="working" theme={theme} size={20} reduced={reduced} />
          </span>
        ) : null}

        <code className="tool-title">{title || 'command'}</code>

        <span className="tool-meta">
          {running ? (
            <Badge tone="live">running</Badge>
          ) : (
            <>
              {isTerminal && r.duration_ms != null && (
                <span className="mono-dim">{r.duration_ms}ms</span>
              )}
              <span className={`status-dot ${ok ? 'ok' : 'bad'}`}>
                {isTerminal ? `exit ${r.exit_code ?? 0}` : ok ? 'ok' : 'failed'}
              </span>
            </>
          )}
          <Icon.Chevron size={14} className={`chev ${open ? 'rot' : ''}`} />
        </span>
      </button>

      {open && (
        <div className="tool-body">
          {!running && isTerminal && <CopyChip text={title} />}
          <pre className="tool-output">{output || 'No output'}</pre>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- artifacts */

export function ArtifactCard({ file, sessionId, onPreview }) {
  const name = typeof file === 'string' ? file : file.filename || file.name;
  const relPath = typeof file === 'string' ? file : file.rel_path;
  const size = typeof file === 'string' ? 0 : file.size_bytes || file.size || 0;
  const href = `/api/workspace/${sessionId}/file?path=${encodeURIComponent(relPath)}`;

  return (
    <div className="artifact">
      <span className="artifact-ext">{fileExt(name)}</span>
      <span className="artifact-info">
        <span className="artifact-name" title={name}>
          {name}
        </span>
        {size > 0 && <span className="artifact-size">{formatBytes(size)}</span>}
      </span>
      <span className="artifact-actions">
        <button type="button" className="mini-btn" onClick={() => onPreview(relPath, name)}>
          <Icon.Eye size={14} />
          View
        </button>
        <a className="mini-btn" href={href} download={name}>
          <Icon.Download size={14} />
          <span className="sr-only">Download {name}</span>
        </a>
      </span>
    </div>
  );
}

/* ----------------------------------------------------------------- errors */

export function ErrorCard({ error }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="error-card" role="alert">
      <div className="error-head">
        <span className="error-icon">
          <Icon.Alert size={16} />
        </span>
        <strong>{error.title || 'Something went wrong'}</strong>
      </div>
      {error.message && <p className="error-message">{error.message}</p>}
      {error.remedy && (
        <p className="error-remedy">
          <b>Fix —</b> {error.remedy}
        </p>
      )}
      {(error.raw || error.message) && (
        <>
          <button type="button" className="link-btn" onClick={() => setOpen((v) => !v)}>
            {open ? 'Hide details' : 'Show details'}
          </button>
          {open && <pre className="error-raw">{error.raw || error.message}</pre>}
        </>
      )}
    </div>
  );
}
