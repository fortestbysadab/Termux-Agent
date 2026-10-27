import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Sidebar from './components/Sidebar.jsx';
import Topbar from './components/Topbar.jsx';
import MessageTurn from './components/MessageTurn.jsx';
import Composer from './components/Composer.jsx';
import WorkspacePanel from './components/WorkspacePanel.jsx';
import ConnectorsView from './components/ConnectorsView.jsx';
import FilesView from './components/FilesView.jsx';
import PreviewModal from './components/PreviewModal.jsx';
import { ConnectorConfigModal, AddMcpModal } from './components/Modals.jsx';
import { OrbSwap } from './components/AgentAvatar.jsx';
import { Icon, Button } from './components/ui.jsx';
import { PHASES } from './activity.js';
import { AGENTS } from './agents.js';
import { useReducedMotion, useResolvedTheme, useMediaQuery } from './util.js';
import * as client from './api.js';

const THEME_KEY = 'termux_agent_theme';

const SUGGESTIONS = [
  { label: 'Build me a 7-day study plan', icon: <Icon.Spark size={15} /> },
  { label: 'Chart AI adoption as an SVG', icon: <Icon.Layers size={15} /> },
  { label: 'Audit the files in this workspace', icon: <Icon.Folder size={15} /> },
];

export default function App() {
  /* ------------------------------------------------------------- chrome */
  const [theme, setTheme] = useState(() => localStorage.getItem(THEME_KEY) || 'system');
  const resolvedTheme = useResolvedTheme(theme);
  const reduced = useReducedMotion();
  const isCompact = useMediaQuery('(max-width: 1024px)');

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(() => window.innerWidth > 1280);
  const [screen, setScreen] = useState('chat');

  /* --------------------------------------------------------------- data */
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [files, setFiles] = useState([]);
  const [connectors, setConnectors] = useState([]);

  /* ------------------------------------------------------------- ui state */
  const [input, setInput] = useState('');
  const [live, setLive] = useState(null); // { phase, detail, runs, error, agent }
  const [startedAt, setStartedAt] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [preview, setPreview] = useState(null);
  const [configTarget, setConfigTarget] = useState(null);
  const [addMcpOpen, setAddMcpOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [booted, setBooted] = useState(false);

  const threadRef = useRef(null);
  const stickToBottom = useRef(true);
  const abortRef = useRef(null);
  // Mirror of the live turn, so stream callbacks can read the accumulated tool
  // runs without stale-closure gymnastics.
  const liveRef = useRef(null);

  /* --------------------------------------------------------------- theme */
  useEffect(() => {
    // data-theme must always be a concrete 'light' | 'dark' so the CSS token
    // blocks (and the Libraries.dev components' `auto` detection) resolve.
    document.documentElement.setAttribute('data-theme', resolvedTheme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme, resolvedTheme]);

  const closeDrawers = useCallback(() => setSidebarOpen(false), []);

  /* ---------------------------------------------------------------- boot */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [list, conns] = await Promise.all([client.getSessions(), client.getConnectors()]);
        if (cancelled) return;
        setSessions(list);
        setConnectors(conns);
        if (list.length > 0) await openSession(list[0].id, { silent: true });
        else await startNewChat({ silent: true });
      } catch (err) {
        console.error('Boot failed', err);
      } finally {
        if (!cancelled) setBooted(true);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ------------------------------------------------------- session verbs */
  async function openSession(id, { silent = false } = {}) {
    setCurrentSessionId(id);
    try {
      const data = await client.getSession(id);
      setMessages(data.messages || []);
      if (!silent) {
        setFiles(await client.getWorkspaceFiles(id));
      } else {
        client.getWorkspaceFiles(id).then(setFiles).catch(() => {});
      }
      stickToBottom.current = true;
    } catch (err) {
      console.error('Failed to open session', err);
    }
  }

  async function startNewChat({ silent = false } = {}) {
    try {
      const session = await client.createSession('New chat');
      setSessions((prev) => [session, ...prev]);
      setCurrentSessionId(session.id);
      setMessages([]);
      setFiles([]);
      setScreen('chat');
      if (!silent) setSidebarOpen(false);
    } catch (err) {
      console.error('Failed to create session', err);
    }
  }

  async function refreshSessions() {
    try {
      setSessions(await client.getSessions());
    } catch {
      /* offline */
    }
  }

  async function refreshFiles() {
    if (!currentSessionId) return;
    try {
      setFiles(await client.getWorkspaceFiles(currentSessionId));
    } catch {
      /* session may be mid-write */
    }
  }

  async function removeSession(id) {
    if (!window.confirm('Delete this conversation and its workspace files?')) return;
    try {
      await client.deleteSession(id);
      const rest = sessions.filter((s) => s.id !== id);
      setSessions(rest);
      if (currentSessionId === id) {
        if (rest.length > 0) await openSession(rest[0].id);
        else await startNewChat({ silent: true });
      }
    } catch (err) {
      window.alert(`Could not delete the conversation: ${err.message}`);
    }
  }

  async function clearAll() {
    if (!window.confirm('Delete every conversation and every workspace file? This cannot be undone.'))
      return;
    try {
      await client.clearSessions();
      setSessions([]);
      await startNewChat({ silent: true });
    } catch (err) {
      window.alert(`Could not clear the history: ${err.message}`);
    }
  }

  /* ----------------------------------------------------------- connectors */
  async function reloadConnectors() {
    try {
      setConnectors(await client.getConnectors());
    } catch {
      /* ignore */
    }
  }

  async function toggleConnector(connector) {
    if (!connector.is_configured && connector.fields?.length > 0) {
      setConfigTarget(connector);
      return;
    }
    try {
      await client.toggleConnector(connector.id, !connector.enabled);
      setConnectors((prev) =>
        prev.map((c) => (c.id === connector.id ? { ...c, enabled: !c.enabled } : c)),
      );
    } catch (err) {
      window.alert(`Could not change the connector: ${err.message}`);
    }
  }

  async function saveConnectorConfig(connector, values) {
    setSaving(true);
    try {
      await client.saveConnectorConfig(connector.id, {
        config: values,
        name: connector.name,
        kind: connector.kind,
        description: connector.description,
      });
      setConfigTarget(null);
      await reloadConnectors();
    } catch (err) {
      window.alert(`Could not save the credentials: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  async function submitCustomMcp(payload) {
    setSaving(true);
    try {
      await client.addCustomMcp(payload);
      setAddMcpOpen(false);
      await reloadConnectors();
    } catch (err) {
      window.alert(`Could not add the MCP server: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  async function deleteConnector(id) {
    if (!window.confirm('Remove this connector?')) return;
    try {
      await client.removeConnector(id);
      setConnectors((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      window.alert(`Could not remove the connector: ${err.message}`);
    }
  }

  /* --------------------------------------------------------------- chat */
  const handleEvent = useCallback((type, data) => {
    const updateLive = (fn) => {
      liveRef.current = fn(liveRef.current);
      setLive(liveRef.current);
    };

    if (type === 'status') {
      updateLive((l) => (l ? { ...l, phase: PHASES.searching, detail: null } : l));
      return;
    }
    if (type === 'command_start') {
      updateLive((l) =>
        l
          ? {
              ...l,
              agent: AGENTS.terminal,
              phase: PHASES.executing,
              detail: data.command,
              runs: [...l.runs, { tool: 'terminal', command: data.command, state: 'running' }],
            }
          : l,
      );
      return;
    }
    if (type === 'command_done') {
      updateLive((l) =>
        l
          ? {
              ...l,
              phase: PHASES.solving,
              detail: null,
              runs: l.runs.map((r) =>
                r.state === 'running' && r.tool === 'terminal'
                  ? { ...data, state: 'done' }
                  : r,
              ),
            }
          : l,
      );
      return;
    }
    if (type === 'connector_start') {
      updateLive((l) =>
        l
          ? {
              ...l,
              agent: AGENTS.connector,
              phase: PHASES.connecting,
              detail: data.tool,
              runs: [...l.runs, { tool: data.tool, state: 'running' }],
            }
          : l,
      );
      return;
    }
    if (type === 'connector_done') {
      updateLive((l) =>
        l
          ? {
              ...l,
              phase: PHASES.solving,
              detail: null,
              runs: l.runs.map((r) =>
                r.state === 'running' && r.tool === data.tool ? { ...data, state: 'done' } : r,
              ),
            }
          : l,
      );
      return;
    }
    if (type === 'error') {
      updateLive((l) => (l ? { ...l, error: data } : l));
      return;
    }
    if (type === 'done') {
      const saved = data.message || {};
      const failed = Boolean(data.error);
      const accumulated = liveRef.current?.runs || [];
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: failed ? '' : saved.content || '',
          created_at: saved.created_at || Date.now() / 1000,
          // The server's own record wins; if it sent none, keep what we streamed
          // so the executed commands stay visible in the transcript.
          tool_runs: data.tool_runs?.length ? data.tool_runs : accumulated,
          files_generated: data.files_generated || [],
          error: data.error || null,
          status: failed ? 'failed' : 'saved',
        },
      ]);
      liveRef.current = null;
      setLive(null);
      refreshFiles();
      refreshSessions();
    }
  }, []);

  const busy = live !== null;

  async function send(text) {
    if (!text || !currentSessionId || busy) return;
    setInput('');
    stickToBottom.current = true;

    const now = Date.now() / 1000;
    setMessages((prev) => [...prev, { role: 'user', content: text, created_at: now }]);
    liveRef.current = {
      phase: PHASES.searching,
      detail: null,
      runs: [],
      error: null,
      agent: AGENTS.assistant,
    };
    setLive(liveRef.current);
    setStartedAt(Date.now());
    setElapsed(0);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await client.streamChat({
        sessionId: currentSessionId,
        text,
        signal: controller.signal,
        onEvent: handleEvent,
      });
    } catch (err) {
      setLive((l) =>
        l
          ? {
              ...l,
              error: {
                title: 'Could not reach the agent',
                message: err.message,
                remedy: 'Check that the Termux Agent server is still running and reachable.',
              },
            }
          : l,
      );
      // Give the user a beat to read the error, then close the live turn.
      setTimeout(() => setLive(null), 1200);
    } finally {
      abortRef.current = null;
    }
  }

  /* elapsed timer for the live activity line */
  useEffect(() => {
    if (!busy) {
      setElapsed(0);
      return undefined;
    }
    const id = setInterval(() => setElapsed(Math.round((Date.now() - startedAt) / 1000)), 1000);
    return () => clearInterval(id);
  }, [busy, startedAt]);

  /* ------------------------------------------------------------ scrolling */
  const onThreadScroll = () => {
    const el = threadRef.current;
    if (!el) return;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
  };

  useEffect(() => {
    const el = threadRef.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages, live]);

  /* ---------------------------------------------------------- shortcuts */
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        startNewChat();
      }
      if (e.key === 'Escape') {
        setSidebarOpen(false);
        if (!isCompact) return;
        setWorkspaceOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCompact]);

  /* ------------------------------------------------------------- derived */
  const activeSession = sessions.find((s) => s.id === currentSessionId);
  const connectorCount = connectors.filter((c) => c.enabled).length;
  const liveTool = live?.runs?.find((r) => r.state === 'running')?.tool;

  const title = useMemo(() => {
    if (screen === 'connectors') return 'Connectors';
    if (screen === 'files') return 'Workspace files';
    return activeSession?.title || 'New chat';
  }, [screen, activeSession]);

  const subtitle = useMemo(() => {
    if (screen === 'connectors') return `${connectorCount} connected`;
    if (screen === 'files') return `${files.length} file${files.length === 1 ? '' : 's'} in this session`;
    return currentSessionId ? `sandbox · ${currentSessionId.slice(0, 8)}` : undefined;
  }, [screen, connectorCount, files.length, currentSessionId]);

  const openPreview = (relPath, filename) => setPreview({ relPath, filename });
  const showSidebar = isCompact ? sidebarOpen : true;

  return (
    <div className={`shell ${workspaceOpen ? 'has-workspace' : ''}`}>
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelect={openSession}
        onNew={startNewChat}
        onDelete={removeSession}
        onClearAll={clearAll}
        screen={screen}
        onScreen={(s) => {
          setScreen(s);
          if (isCompact) setSidebarOpen(false);
        }}
        connectorCount={connectorCount}
        fileCount={files.length}
        theme={theme}
        onTheme={setTheme}
        busy={busy}
        resolvedTheme={resolvedTheme}
        reduced={reduced}
        open={showSidebar}
        onClose={() => setSidebarOpen(false)}
      />

      {isCompact && sidebarOpen && <div className="scrim is-on" onClick={closeDrawers} />}

      <main className="main">
        <Topbar
          title={title}
          subtitle={subtitle}
          screen={screen}
          busy={busy}
          activity={live}
          theme={resolvedTheme}
          reduced={reduced}
          onOpenSidebar={() => setSidebarOpen(true)}
          workspaceOpen={workspaceOpen}
          onToggleWorkspace={() => setWorkspaceOpen((v) => !v)}
          fileCount={files.length}
        />

        <div className="stage">
          {screen === 'chat' && (
            <section className="chat-column" aria-label="Conversation">
              <div className="thread" ref={threadRef} onScroll={onThreadScroll}>
                <div className="thread-inner">
                  {messages.length === 0 && !live && (
                    <EmptyState
                      theme={resolvedTheme}
                      reduced={reduced}
                      onPick={(text) => {
                        setInput(text);
                        document.getElementById('composer-input')?.focus();
                      }}
                      sessionReady={Boolean(currentSessionId)}
                    />
                  )}

                  {messages.map((m, i) => (
                    <MessageTurn
                      key={`${m.created_at}-${i}`}
                      message={m}
                      theme={resolvedTheme}
                      reduced={reduced}
                      sessionId={currentSessionId}
                      onPreview={openPreview}
                    />
                  ))}

                  {live && (
                    <MessageTurn
                      message={{
                        role: 'assistant',
                        created_at: startedAt / 1000,
                        tool_runs: live.runs,
                      }}
                      live
                      activity={live}
                      agent={live.agent}
                      theme={resolvedTheme}
                      reduced={reduced}
                      sessionId={currentSessionId}
                      onPreview={openPreview}
                      elapsed={elapsed}
                    />
                  )}
                </div>
              </div>

              <Composer
                value={input}
                onChange={setInput}
                onSend={send}
                busy={busy}
                theme={resolvedTheme}
                reduced={reduced}
                placeholder={
                  booted
                    ? 'Ask the agent to build, research, or run something…'
                    : 'Starting the agent…'
                }
              />
            </section>
          )}

          {screen === 'connectors' && (
            <ConnectorsView
              connectors={connectors}
              onToggle={toggleConnector}
              onConfigure={(c) => setConfigTarget(c)}
              onAddMcp={() => setAddMcpOpen(true)}
              onDelete={deleteConnector}
              theme={resolvedTheme}
              reduced={reduced}
              liveTool={liveTool}
            />
          )}

          {screen === 'files' && (
            <FilesView
              files={files}
              sessionId={currentSessionId}
              onPreview={openPreview}
              onDownloadZip={() => currentSessionId && window.open(client.zipUrl(currentSessionId), '_blank')}
            />
          )}

          <WorkspacePanel
            open={workspaceOpen}
            onClose={() => setWorkspaceOpen(false)}
            files={files}
            sessionId={currentSessionId}
            onPreview={openPreview}
            onDownloadZip={() =>
              currentSessionId && window.open(client.zipUrl(currentSessionId), '_blank')
            }
          />
        </div>

      </main>

      {workspaceOpen && isCompact && (
        <div className="scrim is-on" onClick={() => setWorkspaceOpen(false)} />
      )}

      <PreviewModal
        target={preview}
        sessionId={currentSessionId}
        onClose={() => setPreview(null)}
      />

      <ConnectorConfigModal
        connector={configTarget}
        onClose={() => setConfigTarget(null)}
        onSubmit={saveConnectorConfig}
        saving={saving}
      />

      <AddMcpModal
        open={addMcpOpen}
        onClose={() => setAddMcpOpen(false)}
        onSubmit={submitCustomMcp}
        saving={saving}
      />
    </div>
  );
}

/* ------------------------------------------------------------- empty hero */

function EmptyState({ theme, reduced, onPick, sessionReady }) {
  return (
    <div className="hero">
      <div className="hero-orb">
        <OrbSwap state="weaving" theme={theme} size={64} reduced={reduced} speed={0.8} />
      </div>
      <h2>Your phone is the workstation.</h2>
      <p>
        Termux Agent plans, runs real shell commands inside this session&apos;s sandbox, and hands
        back finished files. Everything stays on the device.
      </p>
      <div className="hero-chips">
        {SUGGESTIONS.map((s) => (
          <button key={s.label} type="button" className="hero-chip" onClick={() => onPick(s.label)}>
            {s.icon}
            {s.label}
          </button>
        ))}
      </div>
      {!sessionReady && <p className="hero-note">Preparing a session…</p>}
    </div>
  );
}
