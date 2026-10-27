import { Icon, IconButton } from './ui.jsx';
import { OrbSwap } from './AgentAvatar.jsx';

export default function Topbar({
  title,
  subtitle,
  screen,
  busy,
  activity,
  theme,
  reduced,
  onOpenSidebar,
  workspaceOpen,
  onToggleWorkspace,
  fileCount,
}) {
  return (
    <header className="topbar">
      <IconButton label="Open navigation" className="burger" onClick={onOpenSidebar}>
        <Icon.Menu size={19} />
      </IconButton>

      <div className="topbar-title">
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>

      <div className="topbar-right">
        {/* live status: an orb mirrors the exact phase the backend reported */}
        {screen === 'chat' && busy && activity && (
          <div className="status-pill" role="status" aria-live="polite">
            <OrbSwap state={activity.phase.orb} theme={theme} size={20} reduced={reduced} />
            <span>{activity.phase.label}</span>
          </div>
        )}

        <button
          type="button"
          className={`ws-toggle ${workspaceOpen ? 'is-on' : ''}`}
          onClick={onToggleWorkspace}
          aria-pressed={workspaceOpen}
          title="Toggle the session workspace"
        >
          <Icon.Panel size={16} />
          <span className="ws-toggle-label">Workspace</span>
          <span className="count-pill">{fileCount}</span>
        </button>
      </div>
    </header>
  );
}
