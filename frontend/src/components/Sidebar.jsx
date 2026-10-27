import { AgentAvatar } from './AgentAvatar.jsx';
import { AGENTS } from '../agents.js';
import { Icon, IconButton, Segmented } from './ui.jsx';
import { timeAgo } from '../util.js';

export default function Sidebar({
  sessions,
  currentSessionId,
  onSelect,
  onNew,
  onDelete,
  onClearAll,
  screen,
  onScreen,
  connectorCount,
  fileCount,
  theme,
  onTheme,
  busy,
  resolvedTheme,
  reduced,
  open,
  onClose,
}) {
  return (
    <aside className={`sidebar ${open ? 'is-open' : ''}`} aria-label="Navigation">
      <div className="sidebar-brand">
        {/* working ⇄ idle is bound to the real agent state */}
        <AgentAvatar
          agent={AGENTS.assistant}
          state={busy ? 'working' : 'default'}
          size={38}
          theme={resolvedTheme}
          reduced={reduced}
          interactive
        />
        <div className="brand-text">
          <span className="brand-name">Termux Agent</span>
          <span className="brand-sub">
            <i className={`pulse-dot ${busy ? 'busy' : ''}`} />
            {busy ? 'Agent working' : 'Ready'}
          </span>
        </div>
        <IconButton label="Close navigation" className="sidebar-close" onClick={onClose}>
          <Icon.Close size={17} />
        </IconButton>
      </div>

      <button type="button" className="new-chat" onClick={onNew}>
        <Icon.Plus size={17} />
        <span>New chat</span>
        <kbd>⌘K</kbd>
      </button>

      <nav className="nav" aria-label="Sections">
        <button
          type="button"
          className={`nav-item ${screen === 'chat' ? 'is-on' : ''}`}
          aria-current={screen === 'chat' ? 'page' : undefined}
          onClick={() => onScreen('chat')}
        >
          <Icon.Chat size={17} />
          <span>Chat</span>
        </button>
        <button
          type="button"
          className={`nav-item ${screen === 'connectors' ? 'is-on' : ''}`}
          aria-current={screen === 'connectors' ? 'page' : undefined}
          onClick={() => onScreen('connectors')}
        >
          <Icon.Plug size={17} />
          <span>Connectors</span>
          {connectorCount > 0 && <span className="count-pill">{connectorCount}</span>}
        </button>
        <button
          type="button"
          className={`nav-item ${screen === 'files' ? 'is-on' : ''}`}
          aria-current={screen === 'files' ? 'page' : undefined}
          onClick={() => onScreen('files')}
        >
          <Icon.Folder size={17} />
          <span>Workspace files</span>
          {fileCount > 0 && <span className="count-pill">{fileCount}</span>}
        </button>
      </nav>

      <div className="sidebar-section-head">
        <span>Recent</span>
        <span className="sidebar-count">{sessions.length}</span>
      </div>

      <div className="session-list" role="list">
        {sessions.length === 0 && <p className="session-empty">No conversations yet.</p>}
        {sessions.map((s) => (
          <div
            key={s.id}
            role="listitem"
            className={`session ${s.id === currentSessionId ? 'is-on' : ''}`}
          >
            <button
              type="button"
              className="session-main"
              onClick={() => {
                onSelect(s.id);
                onScreen('chat');
              }}
              title={s.title}
            >
              <span className="session-title">{s.title}</span>
              <span className="session-time">
                {s.message_count ? `${s.message_count} msg · ` : ''}
                {timeAgo(s.updated_at)}
              </span>
            </button>
            <button
              type="button"
              className="session-del"
              aria-label={`Delete ${s.title}`}
              title="Delete conversation"
              onClick={() => onDelete(s.id)}
            >
              <Icon.Trash size={14} />
            </button>
          </div>
        ))}
      </div>

      <div className="sidebar-foot">
        <Segmented
          label="Theme"
          value={theme}
          onChange={onTheme}
          options={[
            { value: 'system', icon: <Icon.Monitor size={15} />, label: '' },
            { value: 'light', icon: <Icon.Sun size={15} />, label: '' },
            { value: 'dark', icon: <Icon.Moon size={15} />, label: '' },
          ]}
        />
        <button type="button" className="ghost-btn" onClick={onClearAll}>
          <Icon.Trash size={14} />
          Clear all chats
        </button>
      </div>
    </aside>
  );
}
