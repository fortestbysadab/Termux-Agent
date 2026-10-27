import { useMemo } from 'react';
import { AgentAvatar, ActivityLine } from './AgentAvatar.jsx';
import { ToolRunCard, ArtifactCard, ErrorCard } from './cards.jsx';
import { formatTime, renderMarkdown } from '../util.js';
import { AGENTS } from '../agents.js';
import { Icon } from './ui.jsx';

/**
 * One conversation turn. Assistant turns carry the agent identity, its tool
 * runs, the live activity line (orb), the reply prose, and any artifacts.
 */
export default function MessageTurn({
  message,
  live = false,
  activity,
  agent = AGENTS.assistant,
  theme,
  reduced,
  sessionId,
  onPreview,
  elapsed,
}) {
  const isUser = message.role === 'user';
  // While a turn is streaming, the in-flight run is shown by the activity line;
  // finished runs land here as ordinary cards so nothing disappears on screen.
  const allRuns = message.tool_runs || message.tool_calls || [];
  const runs = live ? allRuns.filter((r) => r.state !== 'running') : allRuns;
  const artifacts = message.files_generated || [];
  const content = useMemo(() => renderMarkdown(message.content), [message.content]);

  if (isUser) {
    return (
      <article className="turn turn-user">
        <div className="turn-main">
          <div className="user-bubble">{message.content}</div>
          {message.uploads?.length > 0 && (
            <div className="user-files">
              {message.uploads.map((f) => (
                <span className="user-file" key={f.rel_path || f.filename}>
                  <Icon.Paperclip size={12} />
                  {f.filename}
                </span>
              ))}
            </div>
          )}
          <div className="turn-head turn-head-user">
            <time>{formatTime(message.created_at)}</time>
          </div>
        </div>
        <div className="turn-avatar user-mark" aria-hidden="true">
          You
        </div>
      </article>
    );
  }

  const avatarState = live ? 'working' : 'default';

  return (
    <article className={`turn turn-agent ${live ? 'is-live' : ''}`}>
      <div className="turn-avatar">
        <AgentAvatar agent={agent} state={avatarState} theme={theme} reduced={reduced} />
      </div>

      <div className="turn-main">
        <header className="turn-head">
          <b>{agent.name}</b>
          <span className="turn-role">{agent.role}</span>
          <time>{formatTime(message.created_at)}</time>
        </header>

        {runs.length > 0 && (
          <div className="tool-list">
            {runs.map((run, i) => (
              <ToolRunCard
                key={`${run.tool}-${i}-${run.command || ''}`}
                run={run}
                theme={theme}
                reduced={reduced}
                index={i}
              />
            ))}
          </div>
        )}

        {live && activity && (
          <ActivityLine
            phase={activity.phase}
            detail={activity.detail}
            theme={theme}
            reduced={reduced}
            elapsed={elapsed}
          />
        )}

        {message.error && <ErrorCard error={message.error} />}

        {content && <div className="prose">{content}</div>}

        {artifacts.length > 0 && (
          <div className="artifact-grid">
            {artifacts.map((file, i) => (
              <ArtifactCard
                key={`${file.rel_path || file}-${i}`}
                file={file}
                sessionId={sessionId}
                onPreview={onPreview}
              />
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
