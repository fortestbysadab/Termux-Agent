import { useEffect, useState } from 'react';
import { Modal, Icon, Button } from './ui.jsx';
import { formatBytes } from '../util.js';

const SPREADSHEET = new Set(['.xlsx', '.xlsm', '.csv', '.tsv']);
const IMAGE = new Set(['.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg']);

/**
 * Rich preview for workspace deliverables. The backend already normalises
 * spreadsheets to row arrays (zipfile + xml.etree, no openpyxl needed), so
 * this component only has to render four shapes: table, pdf, image, text.
 */
export default function PreviewModal({ target, sessionId, onClose }) {
  const [state, setState] = useState({ status: 'idle', data: null, error: null });

  const open = Boolean(target);
  const relPath = target?.relPath;
  const filename = target?.filename || '';
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
  const fileUrl = `/api/workspace/${sessionId}/file?path=${encodeURIComponent(relPath || '')}`;

  useEffect(() => {
    if (!open || !relPath) return undefined;
    let cancelled = false;
    setState({ status: 'loading', data: null, error: null });

    fetch(`/api/workspace/${sessionId}/preview?path=${encodeURIComponent(relPath)}`)
      .then(async (resp) => {
        if (!resp.ok) throw new Error(`Preview unavailable (HTTP ${resp.status})`);
        return resp.json();
      })
      .then((data) => !cancelled && setState({ status: 'ready', data, error: null }))
      .catch(async (err) => {
        // Fall back to the raw bytes rendered as text.
        try {
          const raw = await fetch(fileUrl);
          const text = await raw.text();
          if (!cancelled) {
            setState({ status: 'ready', data: { type: 'text', content: text }, error: null });
          }
        } catch {
          if (!cancelled) setState({ status: 'error', data: null, error: err.message });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [open, relPath, sessionId, fileUrl]);

  const download = (
    <a className="btn btn-primary" href={fileUrl} download={filename}>
      <Icon.Download size={16} />
      Download
    </a>
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={filename || 'Preview'}
      subtitle={ext ? `Workspace deliverable · ${ext.replace('.', '').toUpperCase()}` : undefined}
      size="lg"
      actions={download}
    >
      {state.status === 'loading' && <PreviewSkeleton />}

      {state.status === 'error' && (
        <div className="preview-error">
          <Icon.Alert size={18} />
          <p>{state.error}</p>
        </div>
      )}

      {state.status === 'ready' && state.data?.type === 'spreadsheet' && (
        <SpreadsheetPreview sheet={state.data.sheets?.[0]} name={filename} />
      )}

      {state.status === 'ready' && state.data?.type === 'pdf' && (
        <div className="pdf-card">
          <span className="pdf-glyph">PDF</span>
          <div>
            <h3>{filename}</h3>
            <p>{formatBytes(state.data.size)} · Portable Document Format</p>
          </div>
          <div className="pdf-actions">
            <a className="btn btn-primary" href={fileUrl} target="_blank" rel="noopener noreferrer">
              Open in viewer
            </a>
            <a className="btn btn-ghost" href={fileUrl} download={filename}>
              Save
            </a>
          </div>
        </div>
      )}

      {state.status === 'ready' && state.data?.type === 'image' && (
        <div className="image-preview">
          <img src={fileUrl} alt={filename} />
        </div>
      )}

      {state.status === 'ready' && !['spreadsheet', 'pdf', 'image'].includes(state.data?.type) && (
        <pre className="text-preview">{state.data?.content ?? ''}</pre>
      )}
    </Modal>
  );
}

function SpreadsheetPreview({ sheet, name }) {
  const rows = sheet?.rows || [];
  if (rows.length === 0) {
    return <p className="preview-empty">{name} is empty.</p>;
  }
  const [head, ...body] = rows;
  return (
    <div className="sheet">
      <div className="sheet-head">
        <strong>{sheet.name}</strong>
        <span className="meta">{rows.length} rows × {head.length} cols</span>
      </div>
      <div className="sheet-scroll">
        <table>
          <thead>
            <tr>
              {head.map((cell, i) => (
                <th key={i}>{cell}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((row, r) => (
              <tr key={r}>
                {head.map((_, c) => (
                  <td key={c}>{row[c] ?? ''}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PreviewSkeleton() {
  return (
    <div className="preview-skeleton" aria-live="polite">
      {[0, 1, 2, 3].map((i) => (
        <span key={i} style={{ width: `${92 - i * 14}%` }} />
      ))}
    </div>
  );
}
