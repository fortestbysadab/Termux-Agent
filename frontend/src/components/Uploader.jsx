import { useCallback, useEffect, useRef, useState } from 'react';
import { uploadFiles } from '../api.js';
import { Icon } from './ui.jsx';
import { formatBytes } from '../util.js';

/**
 * File uploads.
 *
 * Files go to `<session workspace>/uploads/` — the same sandbox the agent's
 * shell runs in — so the model can read them with ordinary commands, they ride
 * along in the workspace ZIP, and they vanish with the session.
 *
 * Three ways in: the paperclip, drag & drop anywhere on the thread, and paste.
 */
export function useUploader({ sessionId, onUploaded, onError }) {
  const [queue, setQueue] = useState([]); // {id, name, size, status, progress, error}
  const inputRef = useRef(null);

  const run = useCallback(
    async (fileList) => {
      if (!sessionId || !fileList?.length) return;
      const files = Array.from(fileList);
      const entries = files.map((f) => ({
        id: `${f.name}-${f.size}-${Math.random().toString(36).slice(2, 7)}`,
        name: f.name,
        size: f.size,
        status: 'uploading',
        progress: 0,
        error: null,
      }));
      setQueue((q) => [...q, ...entries]);

      try {
        const stored = await uploadFiles(sessionId, files, (fraction) => {
          setQueue((q) => q.map((item) => (entries.some((e) => e.id === item.id) ? { ...item, progress: fraction } : item)));
        });
        setQueue((q) =>
          q.map((item) =>
            entries.some((e) => e.id === item.id) ? { ...item, status: 'done', progress: 1 } : item,
          ),
        );
        onUploaded?.(stored);
        // let the chips linger briefly, then clear
        setTimeout(() => setQueue((q) => q.filter((item) => !entries.some((e) => e.id === item.id))), 2600);
      } catch (err) {
        setQueue((q) =>
          q.map((item) =>
            entries.some((e) => e.id === item.id)
              ? { ...item, status: 'error', error: err.message }
              : item,
          ),
        );
        onError?.(err.message);
      }
    },
    [sessionId, onUploaded, onError],
  );

  return { queue, run, inputRef, dismiss: (id) => setQueue((q) => q.filter((i) => i.id !== id)) };
}

export function UploadChips({ queue, onDismiss }) {
  if (!queue.length) return null;
  return (
    <ul className="upload-chips" aria-live="polite">
      {queue.map((item) => (
        <li key={item.id} className={`upload-chip is-${item.status}`}>
          <span className="upload-chip-icon">
            {item.status === 'error' ? <Icon.Alert size={14} /> : <Icon.Folder size={14} />}
          </span>
          <span className="upload-chip-body">
            <span className="upload-chip-name" title={item.name}>
              {item.name}
            </span>
            <span className="upload-chip-meta">
              {item.status === 'error'
                ? item.error
                : item.status === 'done'
                  ? `${formatBytes(item.size)} · saved to uploads/`
                  : `${formatBytes(item.size)} · ${Math.round(item.progress * 100)}%`}
            </span>
            {item.status === 'uploading' && (
              <span className="upload-bar" aria-hidden="true">
                <i style={{ width: `${Math.round(item.progress * 100)}%` }} />
              </span>
            )}
          </span>
          <button
            type="button"
            className="upload-chip-x"
            aria-label={`Dismiss ${item.name}`}
            onClick={() => onDismiss(item.id)}
          >
            <Icon.Close size={13} />
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Drag-and-drop shell: wraps the thread and shows a drop target while hovering. */
export function DropZone({ disabled, onFiles, children }) {
  const [over, setOver] = useState(false);
  const depth = useRef(0);

  useEffect(() => {
    const prevent = (e) => {
      // Only intercept when files are actually being dragged.
      if (e.dataTransfer?.types?.includes('Files')) e.preventDefault();
    };
    window.addEventListener('dragover', prevent);
    window.addEventListener('drop', prevent);
    return () => {
      window.removeEventListener('dragover', prevent);
      window.removeEventListener('drop', prevent);
    };
  }, []);

  return (
    <div
      className={`dropzone ${over ? 'is-over' : ''}`}
      onDragEnter={(e) => {
        if (disabled || !e.dataTransfer?.types?.includes('Files')) return;
        depth.current += 1;
        setOver(true);
      }}
      onDragOver={(e) => {
        if (!disabled && e.dataTransfer?.types?.includes('Files')) e.preventDefault();
      }}
      onDragLeave={() => {
        depth.current = Math.max(0, depth.current - 1);
        if (depth.current === 0) setOver(false);
      }}
      onDrop={(e) => {
        if (disabled) return;
        e.preventDefault();
        depth.current = 0;
        setOver(false);
        if (e.dataTransfer?.files?.length) onFiles(e.dataTransfer.files);
      }}
    >
      {children}
      {over && (
        <div className="drop-overlay">
          <div className="drop-card">
            <Icon.Folder size={24} />
            <b>Drop to add to this session</b>
            <span>Files land in uploads/ and the agent can read them.</span>
          </div>
        </div>
      )}
    </div>
  );
}
