import { useMemo, useState } from 'react';
import { Icon, Button } from './ui.jsx';
import { formatBytes, fileExt } from '../util.js';

export default function FilesView({ files, sessionId, onPreview, onDownloadZip }) {
  const [filter, setFilter] = useState('');

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? files.filter((f) => f.name.toLowerCase().includes(q)) : files;
  }, [files, filter]);

  const total = files.reduce((s, f) => s + (f.size || 0), 0);

  return (
    <section className="screen" aria-label="Workspace files">
      <div className="screen-head">
        <div>
          <h2>Workspace files</h2>
          <p>
            Everything the agent produced in this session — {files.length} file
            {files.length === 1 ? '' : 's'}, {formatBytes(total)}. Nothing leaves the device.
          </p>
        </div>
        <Button variant="primary" onClick={onDownloadZip} disabled={files.length === 0}>
          <Icon.Zip size={16} />
          Download ZIP
        </Button>
      </div>

      <div className="filter-row">
        <span className="filter-icon">
          <Icon.Search size={16} />
        </span>
        <input
          className="filter-input"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter files by name…"
          aria-label="Filter files by name"
        />
        {filter && (
          <button type="button" className="mini-btn" onClick={() => setFilter('')}>
            <Icon.Close size={14} />
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <span className="empty-glyph">
            <Icon.Folder size={26} />
          </span>
          <h3>{filter ? 'No matching files' : 'No files yet'}</h3>
          <p>
            {filter
              ? 'Try a different search term.'
              : 'Ask the agent for a document, a chart, or a script and it will show up here.'}
          </p>
        </div>
      ) : (
        <div className="file-grid">
          {filtered.map((f, i) => {
            const href = `/api/workspace/${sessionId}/file?path=${encodeURIComponent(f.rel_path)}`;
            return (
              <article className="file-card" key={f.rel_path} style={{ '--i': i }}>
                <span className="file-ext">{fileExt(f.name)}</span>
                <div className="file-card-body">
                  <h3 title={f.name}>{f.name}</h3>
                  <span className="meta">{formatBytes(f.size)}</span>
                </div>
                <div className="file-card-actions">
                  <button
                    type="button"
                    className="mini-btn"
                    onClick={() => onPreview(f.rel_path, f.name)}
                  >
                    <Icon.Eye size={14} />
                    View
                  </button>
                  <a className="mini-btn" href={href} download={f.name}>
                    <Icon.Download size={14} />
                    <span className="sr-only">Download {f.name}</span>
                  </a>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
