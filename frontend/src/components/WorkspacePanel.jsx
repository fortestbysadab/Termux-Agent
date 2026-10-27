import { Fragment } from 'react';
import { Icon, IconButton } from './ui.jsx';
import { formatBytes, fileExt } from '../util.js';

const QUOTA = 128 * 1024 * 1024;

export default function WorkspacePanel({ open, onClose, files, sessionId, onPreview, onDownloadZip }) {
  const total = files.reduce((sum, f) => sum + (f.size || 0), 0);
  const pct = Math.min(100, (total / QUOTA) * 100);

  return (
    <aside
      className={`workspace ${open ? 'is-open' : ''}`}
      aria-label="Session workspace"
      aria-hidden={!open}
    >
      <header className="workspace-head">
        <div>
          <h2>Workspace</h2>
          <p className="workspace-quota">
            {formatBytes(total)} / 128 MB · {files.length} file{files.length === 1 ? '' : 's'}
          </p>
        </div>
        <div className="workspace-head-actions">
          <IconButton
            label="Download workspace as ZIP"
            onClick={() => onDownloadZip()}
            disabled={files.length === 0}
          >
            <Icon.Zip size={17} />
          </IconButton>
          <IconButton label="Close workspace" onClick={onClose}>
            <Icon.Close size={17} />
          </IconButton>
        </div>
      </header>

      <div className="quota-bar" aria-hidden="true">
        <i style={{ width: `${Math.max(pct, files.length ? 2 : 0)}%` }} />
      </div>

      <div className="workspace-section">
        <div className="workspace-section-head">
          <span>Runtime</span>
        </div>
        <div className="runtime-row">
          <i className="pulse-dot busy" />
          <span>Termux Agent server</span>
          <code>:8080</code>
        </div>
        <div className="runtime-row">
          <i className="pulse-dot" />
          <span>Session sandbox</span>
          <code>{sessionId ? sessionId.slice(0, 8) : '—'}</code>
        </div>
      </div>

      <div className="workspace-section grow">
        <div className="workspace-section-head">
          <span>Files</span>
          <span className="sidebar-count">{files.length}</span>
        </div>

        {files.length === 0 ? (
          <p className="workspace-empty">
            Nothing here yet. Ask the agent for a document, chart, or script and it will appear in
            this session&apos;s sandbox.
          </p>
        ) : (
          <ul className="ws-tree">
            {files.map((f, i) => {
              const href = `/api/workspace/${sessionId}/file?path=${encodeURIComponent(f.rel_path)}`;
              const isUpload = f.rel_path.startsWith('uploads/');
              const prev = files[i - 1];
              const groupStart = i === 0 || (prev && prev.rel_path.startsWith('uploads/') !== isUpload);
              return (
                <Fragment key={f.rel_path}>
                {groupStart && (
                  <li className="ws-group-label" aria-hidden="true">
                    {isUpload ? 'Uploads' : 'Agent output'}
                  </li>
                )}
                <li key={f.rel_path} className={`ws-file ${isUpload ? 'is-upload' : ''}`}>
                  <span className="ws-ext">{fileExt(f.name)}</span>
                  <span className="ws-file-info">
                    <span className="ws-file-name" title={f.name}>
                      {f.name}
                    </span>
                    <span className="ws-file-size">{formatBytes(f.size)}</span>
                  </span>
                  <span className="ws-file-actions">
                    <button
                      type="button"
                      className="mini-btn"
                      onClick={() => onPreview(f.rel_path, f.name)}
                    >
                      <Icon.Eye size={14} />
                    </button>
                    <a className="mini-btn" href={href} download={f.name} title={`Download ${f.name}`}>
                      <Icon.Download size={14} />
                    </a>
                  </span>
                </li>
                </Fragment>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
