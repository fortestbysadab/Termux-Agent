import { useEffect, useRef, useState } from 'react';

/* ------------------------------------------------------------------ icons */
/* Hairline 1.6px strokes, 24px box, currentColor — one visual language. */

const Svg = ({ children, size = 18, ...rest }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    focusable="false"
    {...rest}
  >
    {children}
  </svg>
);

export const Icon = {
  Chat: (p) => (
    <Svg {...p}>
      <path d="M20 12a8 8 0 0 1-8 8H7l-4 2 1.2-3.6A8 8 0 1 1 20 12Z" />
    </Svg>
  ),
  Plug: (p) => (
    <Svg {...p}>
      <path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-6 6 6 6 0 0 1-6-6V8ZM12 17v4" />
    </Svg>
  ),
  Folder: (p) => (
    <Svg {...p}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
    </Svg>
  ),
  Plus: (p) => (
    <Svg {...p}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  ),
  Close: (p) => (
    <Svg {...p}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  ),
  Menu: (p) => (
    <Svg {...p}>
      <path d="M4 7h16M4 12h16M4 17h11" />
    </Svg>
  ),
  Send: (p) => (
    <Svg {...p}>
      <path d="M4.5 12h13M13 6.5 19 12l-6 5.5" />
    </Svg>
  ),
  Download: (p) => (
    <Svg {...p}>
      <path d="M12 4v10m0 0 4-4m-4 4-4-4M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" />
    </Svg>
  ),
  Eye: (p) => (
    <Svg {...p}>
      <path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="2.6" />
    </Svg>
  ),
  Trash: (p) => (
    <Svg {...p}>
      <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13M10 11v5M14 11v5" />
    </Svg>
  ),
  Terminal: (p) => (
    <Svg {...p}>
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <path d="M7.5 10l2.5 2-2.5 2M13 14h4" />
    </Svg>
  ),
  Chevron: (p) => (
    <Svg {...p}>
      <path d="M9 6l6 6-6 6" />
    </Svg>
  ),
  Sun: (p) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.2 5.2l1.4 1.4M17.4 17.4l1.4 1.4M18.8 5.2l-1.4 1.4M6.6 17.4l-1.4 1.4" />
    </Svg>
  ),
  Moon: (p) => (
    <Svg {...p}>
      <path d="M20 14.2A8.2 8.2 0 0 1 9.8 4a8.4 8.4 0 1 0 10.2 10.2Z" />
    </Svg>
  ),
  Monitor: (p) => (
    <Svg {...p}>
      <rect x="3" y="4.5" width="18" height="12" rx="2" />
      <path d="M9 20h6M12 16.5V20" />
    </Svg>
  ),
  Alert: (p) => (
    <Svg {...p}>
      <path d="M12 4.5 21 19.5H3L12 4.5Z" />
      <path d="M12 10v4M12 16.6v.4" />
    </Svg>
  ),
  Check: (p) => (
    <Svg {...p}>
      <path d="M5 12.5 9.5 17 19 6.5" />
    </Svg>
  ),
  Search: (p) => (
    <Svg {...p}>
      <circle cx="11" cy="11" r="6" />
      <path d="M15.5 15.5 20 20" />
    </Svg>
  ),
  Layers: (p) => (
    <Svg {...p}>
      <path d="M12 3.5 21 8l-9 4.5L3 8l9-4.5ZM3 12.2 12 16.7l9-4.5M3 16.4 12 21l9-4.6" />
    </Svg>
  ),
  Spark: (p) => (
    <Svg {...p}>
      <path d="M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1L5 10.5l5.1-1.9L12 3.5Z" />
    </Svg>
  ),
  Bolt: (p) => (
    <Svg {...p}>
      <path d="M13 2.5 4.5 13.5H11l-1 8 8.5-11H12l1-8Z" />
    </Svg>
  ),
  Cpu: (p) => (
    <Svg {...p}>
      <rect x="7" y="7" width="10" height="10" rx="2" />
      <path d="M10 3v3M14 3v3M10 18v3M14 18v3M3 10h3M3 14h3M18 10h3M18 14h3" />
    </Svg>
  ),
  Zip: (p) => (
    <Svg {...p}>
      <path d="M5 4h14v16H5V4Z" />
      <path d="M12 4v3M12 9v2M12 13v3" />
    </Svg>
  ),
  Paperclip: (p) => (
    <Svg {...p}>
      <path d="M20 11.5 12 19.5a4.6 4.6 0 0 1-6.5-6.5l8-8a3 3 0 0 1 4.3 4.3l-8 8a1.4 1.4 0 0 1-2-2l7-7" />
    </Svg>
  ),
  Sparkle: (p) => (
    <Svg {...p}>
      <path d="M12 3.5l1.6 4.4 4.4 1.6-4.4 1.6L12 15.5l-1.6-4.4L6 9.5l4.4-1.6L12 3.5ZM18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" />
    </Svg>
  ),
  Panel: (p) => (
    <Svg {...p}>
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <path d="M15 4v16" />
    </Svg>
  ),
};

/* --------------------------------------------------------------- controls */

export function IconButton({ label, active = false, className = '', children, ...rest }) {
  return (
    <button
      type="button"
      className={`icon-btn ${active ? 'is-active' : ''} ${className}`}
      aria-label={label}
      title={label}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Button({ variant = 'ghost', className = '', children, ...rest }) {
  return (
    <button type="button" className={`btn btn-${variant} ${className}`} {...rest}>
      {children}
    </button>
  );
}

export function Badge({ children, tone = 'neutral' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

/* ---------------------------------------------------------------- dialogs */

export function Modal({ open, onClose, title, subtitle, size = 'md', actions, children }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    document.addEventListener('keydown', onKey);
    const previous = document.activeElement;
    // Focus the first focusable element for keyboard users.
    requestAnimationFrame(() => {
      const node = ref.current?.querySelector(
        'input, textarea, select, button:not([data-close]), [href]',
      );
      node?.focus?.();
    });
    return () => {
      document.removeEventListener('keydown', onKey);
      previous?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div
        className={`modal modal-${size}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
      >
        <header className="modal-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p className="modal-sub">{subtitle}</p>}
          </div>
          <div className="modal-head-actions">
            {actions}
            <IconButton label="Close" data-close onClick={onClose}>
              <Icon.Close size={17} />
            </IconButton>
          </div>
        </header>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- form parts */

export function Field({ label, hint, children, htmlFor }) {
  return (
    <label className="field" htmlFor={htmlFor}>
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function Segmented({ value, onChange, options, label }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={`segmented-item ${value === opt.value ? 'is-on' : ''}`}
          aria-pressed={value === opt.value}
          onClick={() => onChange(opt.value)}
        >
          {opt.icon}
          {opt.label && <span>{opt.label}</span>}
        </button>
      ))}
    </div>
  );
}

/** Copy-to-clipboard chip used on command headers. */
export function CopyChip({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="copy-chip"
      onClick={async (e) => {
        e.stopPropagation();
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        } catch {
          /* clipboard unavailable */
        }
      }}
      title="Copy"
    >
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}
