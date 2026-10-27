import { useEffect, useRef } from 'react';
import { BorderBeam } from 'border-beam';
import { Icon } from './ui.jsx';

/**
 * The chat composer.
 *
 * ── Border Beam lives here and nowhere else. ──
 * It wraps only this element: a slow, low-strength "ocean" beam at rest that
 * brightens and speeds up while the agent is working. Everything inside keeps
 * its native behaviour (focus, caret, IME, autosize, Enter to send, paste).
 */
export default function Composer({
  value,
  onChange,
  onSend,
  onAttach,
  onPasteFiles,
  busy,
  uploading,
  attachmentCount = 0,
  theme,
  reduced,
  placeholder = 'Ask the agent to build, research, or run something…',
}) {
  const textareaRef = useRef(null);

  // Autosize: grow with content, cap at ~9 lines, then scroll.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  const canSend = (value.trim().length > 0 || attachmentCount > 0) && !busy && !uploading;

  const submit = () => {
    if (!canSend) return;
    onSend(value.trim());
  };

  // The beam needs a little more push on a white surface to read as a glow.
  const light = theme === 'light';
  const beam = busy
    ? { strength: 1, brightness: light ? 1.26 : 1.34, saturation: 1.3, glow: 1.1, duration: 2.6 }
    : {
        strength: light ? 0.92 : 0.62,
        brightness: light ? 1.3 : 1.16,
        saturation: light ? 1.16 : 1.08,
        glow: 0.95,
        duration: 5.2,
      };

  return (
    <div className="composer-wrap">
      <BorderBeam
        colorVariant="ocean"
        theme={theme}
        borderRadius={20}
        duration={beam.duration}
        strength={beam.strength}
        brightness={beam.brightness}
        saturation={beam.saturation}
        glowSize={beam.glow}
        active={!reduced}
        className="composer-beam"
      >
        <div className={`composer ${busy ? 'is-busy' : ''}`}>
          <label className="sr-only" htmlFor="composer-input">
            Message the agent
          </label>
          <textarea
            id="composer-input"
            ref={textareaRef}
            className="composer-input"
            rows={1}
            value={value}
            placeholder={placeholder}
            spellCheck="false"
            autoComplete="off"
            onChange={(e) => onChange(e.target.value)}
            onPaste={(e) => {
              const files = Array.from(e.clipboardData?.files || []);
              if (files.length) {
                e.preventDefault();
                onPasteFiles?.(files);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <div className="composer-bar">
            <button
              type="button"
              className="attach-btn"
              onClick={onAttach}
              disabled={busy}
              title="Attach a file to this session"
              aria-label="Attach a file"
            >
              <Icon.Paperclip size={16} />
            </button>

            <span className="composer-hint">
              {attachmentCount > 0 ? (
                <>
                  <b>{attachmentCount}</b> file{attachmentCount === 1 ? '' : 's'} attached ·{' '}
                </>
              ) : null}
              <kbd>Enter</kbd> send · <kbd>Shift</kbd>+<kbd>Enter</kbd> newline
            </span>

            <button
              type="button"
              className="send-btn"
              onClick={submit}
              disabled={!canSend}
              aria-label={busy ? 'Agent is working' : uploading ? 'Uploading file' : 'Send message'}
              title={busy ? 'Agent is working…' : uploading ? 'Uploading…' : 'Send (Enter)'}
            >
              {uploading ? <span className="spinner" /> : <Icon.Send size={18} />}
            </button>
          </div>
        </div>
      </BorderBeam>
      <p className="composer-foot">
        Files you attach are saved to <code>uploads/</code> inside this session&rsquo;s sandbox — the
        agent can read them, and they leave with the session.
      </p>
    </div>
  );
}
