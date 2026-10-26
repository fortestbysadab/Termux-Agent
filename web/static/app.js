// Termux Agent — Clean Frontend Client matching Android Agent Design

const state = {
  currentSessionId: null,
  activeScreen: 'chat',
  sessions: [],
  connectors: [],
  workspaceFiles: [],
};

// --- DOM References ---
const sidebar = document.getElementById('sidebar');
const scrim = document.getElementById('scrim');
const burgerBtn = document.getElementById('burgerBtn');
const topbarTitle = document.getElementById('topbarTitle');
const newChatBtn = document.getElementById('newChatBtn');
const clearAllChatsBtn = document.getElementById('clearAllChatsBtn');
const sessionsList = document.getElementById('sessionsList');

// Screens & Tabs
const navChat = document.getElementById('navChat');
const navConnectors = document.getElementById('navConnectors');
const navFiles = document.getElementById('navFiles');
const chatScreen = document.getElementById('chatScreen');
const connectorsScreen = document.getElementById('connectorsScreen');
const filesScreen = document.getElementById('filesScreen');

// Chat DOM
const threadContainer = document.getElementById('threadContainer');
const messagesList = document.getElementById('messagesList');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');

// Badges
const activeConnectorsBadge = document.getElementById('activeConnectorsBadge');
const workspaceFilesBadge = document.getElementById('workspaceFilesBadge');

// Files Screen
const fileFilterInput = document.getElementById('fileFilterInput');
const workspaceFilesList = document.getElementById('workspaceFilesList');

// Connectors Screen
const connectorsList = document.getElementById('connectorsList');
const openAddMcpBtn = document.getElementById('openAddMcpBtn');

// Modals
const connectorConfigModal = document.getElementById('connectorConfigModal');
const configConnectorName = document.getElementById('configConnectorName');
const configConnectorId = document.getElementById('configConnectorId');
const configFormFields = document.getElementById('configFormFields');
const closeConfigModalBtn = document.getElementById('closeConfigModalBtn');
const cancelConfigBtn = document.getElementById('cancelConfigBtn');
const connectorConfigForm = document.getElementById('connectorConfigForm');

const addMcpModal = document.getElementById('addMcpModal');
const closeAddMcpModalBtn = document.getElementById('closeAddMcpModalBtn');
const cancelAddMcpBtn = document.getElementById('cancelAddMcpBtn');
const addMcpForm = document.getElementById('addMcpForm');
const mcpKind = document.getElementById('mcpKind');
const mcpCommandGroup = document.getElementById('mcpCommandGroup');
const mcpUrlGroup = document.getElementById('mcpUrlGroup');

const filePreviewModal = document.getElementById('filePreviewModal');
const previewFileName = document.getElementById('previewFileName');
const previewFileContent = document.getElementById('previewFileContent');
const downloadPreviewBtn = document.getElementById('downloadPreviewBtn');
const closePreviewBtn = document.getElementById('closePreviewBtn');

// Theme Picker
const themePicker = document.getElementById('themePicker');

// --- Helper Functions ---
function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatTime(timestamp) {
  if (!timestamp) return '';
  const d = new Date(timestamp * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function getConnectorEmoji(id) {
  const map = {
    github: '🐙',
    drive: '📁',
    docs: '📄',
    notion: '📓',
    gmail: '✉️',
    linear: '📐',
    calendar: '📅',
    slides: '📊',
    sheets: '📈',
    dropbox: '📦',
    vercel: '▲',
    supabase: '⚡',
  };
  return map[id.toLowerCase()] || '🔌';
}

function renderMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Code blocks ```code```
  html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre><code>${code.trim()}</code></pre>`;
  });

  // Inline code `code`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Italics *text*
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Paragraphs
  html = html.split('\n\n').map(p => {
    p = p.trim();
    if (p.startsWith('<pre') || p.startsWith('<h') || p.startsWith('<ul>')) return p;
    return `<p>${p.replace(/\n/g, '<br>')}</p>`;
  }).join('');

  return html;
}

// --- API Helper ---
async function api(path, options = {}) {
  const resp = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error || `HTTP ${resp.status}`);
  }
  return await resp.json();
}

// --- Screen Switching ---
function switchScreen(screen) {
  state.activeScreen = screen;

  // Tabs
  navChat.classList.toggle('active', screen === 'chat');
  navChat.setAttribute('aria-current', screen === 'chat' ? 'page' : 'false');
  navConnectors.classList.toggle('active', screen === 'connectors');
  navConnectors.setAttribute('aria-current', screen === 'connectors' ? 'page' : 'false');
  navFiles.classList.toggle('active', screen === 'files');
  navFiles.setAttribute('aria-current', screen === 'files' ? 'page' : 'false');

  // Screens
  chatScreen.classList.toggle('hidden', screen !== 'chat');
  connectorsScreen.classList.toggle('hidden', screen !== 'connectors');
  filesScreen.classList.toggle('hidden', screen !== 'files');

  if (screen === 'connectors') {
    topbarTitle.textContent = 'Connectors';
    loadConnectors();
  } else if (screen === 'files') {
    topbarTitle.textContent = 'Workspace Files';
    loadWorkspaceFiles();
  } else {
    const s = state.sessions.find(x => x.id === state.currentSessionId);
    topbarTitle.textContent = s ? s.title : 'Chat';
    scrollToBottom();
  }

  // Close mobile sidebar if open
  sidebar.classList.remove('open');
  scrim.classList.remove('open');
}

// --- Sessions Management ---
async function loadSessions() {
  try {
    const data = await api('/api/sessions');
    state.sessions = data.sessions || [];
    renderSessionsList();

    if (state.sessions.length > 0 && !state.currentSessionId) {
      selectSession(state.sessions[0].id);
    } else if (state.sessions.length === 0) {
      createNewSession();
    }
  } catch (err) {
    console.error('Failed to load sessions:', err);
  }
}

function renderSessionsList() {
  sessionsList.innerHTML = '';
  state.sessions.forEach(session => {
    const wrap = document.createElement('div');
    wrap.className = `histitem-wrap ${session.id === state.currentSessionId ? 'on' : ''}`;
    wrap.innerHTML = `
      <button class="histitem" title="${escapeHtml(session.title)}">${escapeHtml(session.title)}</button>
      <button class="histitem-del" title="Delete conversation" data-id="${session.id}">✕</button>
    `;

    wrap.querySelector('.histitem').addEventListener('click', () => {
      selectSession(session.id);
      switchScreen('chat');
    });

    wrap.querySelector('.histitem-del').addEventListener('click', (e) => {
      e.stopPropagation();
      deleteSession(session.id);
    });

    sessionsList.appendChild(wrap);
  });
}

async function selectSession(sessionId) {
  state.currentSessionId = sessionId;
  renderSessionsList();

  try {
    const data = await api(`/api/sessions/${sessionId}`);
    topbarTitle.textContent = data.session.title || 'Chat';
    renderMessages(data.messages || []);
    loadWorkspaceFiles();
  } catch (err) {
    console.error('Failed to load session details:', err);
  }
}

async function createNewSession() {
  try {
    const data = await api('/api/sessions', {
      method: 'POST',
      body: JSON.stringify({ title: 'New chat' }),
    });
    state.sessions.unshift(data.session);
    selectSession(data.session.id);
    switchScreen('chat');
    chatInput.focus();
  } catch (err) {
    console.error('Failed to create session:', err);
  }
}

async function deleteSession(sessionId) {
  if (!confirm('Are you sure you want to delete this chat and its workspace?')) return;
  try {
    await api(`/api/sessions/${sessionId}`, { method: 'DELETE' });
    state.sessions = state.sessions.filter(s => s.id !== sessionId);
    if (state.currentSessionId === sessionId) {
      state.currentSessionId = null;
      if (state.sessions.length > 0) {
        selectSession(state.sessions[0].id);
      } else {
        createNewSession();
      }
    } else {
      renderSessionsList();
    }
  } catch (err) {
    alert('Failed to delete session: ' + err.message);
  }
}

async function clearAllChats() {
  if (!confirm('Delete ALL chat history and workspace files? This cannot be undone.')) return;
  try {
    await api('/api/sessions', { method: 'DELETE' });
    state.sessions = [];
    createNewSession();
  } catch (err) {
    alert('Failed to clear chats: ' + err.message);
  }
}

// --- Messages & Chat Rendering ---
function renderMessages(messages) {
  messagesList.innerHTML = '';
  if (messages.length === 0) {
    messagesList.innerHTML = `
      <div class="empty">
        <div style="font-size: 32px; margin-block-end: 8px;">⚡</div>
        <b>Termux Agent is ready.</b><br>
        Ask anything, or run terminal commands to install packages, build scripts, or create documents.
      </div>
    `;
    return;
  }

  messages.forEach(msg => {
    appendMessageToDom(msg);
  });
  scrollToBottom();
}

function appendMessageToDom(msg) {
  const turnEl = document.createElement('div');
  const isUser = msg.role === 'user';
  turnEl.className = `turn ${isUser ? 'user' : ''}`;

  if (isUser) {
    turnEl.innerHTML = `
      <div class="body">
        <div class="userbubble">${escapeHtml(msg.content)}</div>
        <div class="byline" style="margin-block: 4px 0;"><time>${formatTime(msg.created_at)}</time></div>
      </div>
      <div class="avatar me">You</div>
    `;
    messagesList.appendChild(turnEl);
    return;
  }

  // Assistant turn
  let toolRunsHtml = '';
  if (msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0) {
    toolRunsHtml = msg.tool_calls.map(tc => {
      const detail = tc.detail || {};
      const isTerminal = detail.tool === 'terminal';
      const cmdOrTool = isTerminal ? detail.command : (detail.tool || tc.name);
      const isOk = detail.ok !== false;
      const statusBadge = isTerminal ? `Exit ${detail.exit_code}` : (isOk ? 'OK' : 'Error');
      const output = isTerminal ? `${detail.stdout || ''}${detail.stderr ? '\n' + detail.stderr : ''}` : JSON.stringify(detail.result, null, 2);

      return `
        <div class="filecard" style="margin-block-end: 10px; font-family: ui-monospace, Menlo, Consolas, monospace;">
          <div class="filecard-head" style="cursor: pointer;" onclick="this.nextElementSibling.classList.toggle('hidden')">
            <span class="filechip" style="background: ${isOk ? 'var(--accent-soft)' : 'color-mix(in srgb, var(--danger) 15%, transparent)'}; color: ${isOk ? 'var(--accent)' : 'var(--danger)'};">
              ${isTerminal ? '$ BASH' : '🔌 MCP'}
            </span>
            <span class="filename" style="font-weight: 550;">${escapeHtml(cmdOrTool)}</span>
            <span class="opens" style="color: ${isOk ? 'var(--ok)' : 'var(--danger)'}; font-size: 11px;">
              ${statusBadge} ▾
            </span>
          </div>
          <div class="filepreview hidden" style="padding: 12px 14px; background: var(--soft-bg); font-size: 12px; white-space: pre-wrap; max-height: 250px; overflow-y: auto;">${escapeHtml(output || 'No output')}</div>
        </div>
      `;
    }).join('');
  }

  let artifactsHtml = '';
  if (msg.files_generated && Array.isArray(msg.files_generated) && msg.files_generated.length > 0) {
    artifactsHtml = msg.files_generated.map(file => {
      const name = typeof file === 'string' ? file : file.filename;
      const relPath = typeof file === 'string' ? file : file.rel_path;
      const ext = name.split('.').pop() || 'file';
      const size = file.size_bytes ? formatBytes(file.size_bytes) : '';
      const href = `/api/workspace/${state.currentSessionId}/file?path=${encodeURIComponent(relPath)}`;

      return `
        <div class="filecard">
          <div class="filecard-head">
            <span class="filechip">${ext.toUpperCase()}</span>
            <span class="filename">${escapeHtml(name)} ${size ? `(${size})` : ''}</span>
            <div style="margin-inline-start: auto; display: flex; gap: 8px;">
              <button class="opens preview-btn" data-path="${escapeHtml(relPath)}" data-name="${escapeHtml(name)}" style="background:none;border:0;cursor:pointer;">View</button>
              <a class="opens" href="${href}" download="${escapeHtml(name)}">Download</a>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  turnEl.innerHTML = `
    <div class="avatar bot">T</div>
    <div class="body">
      <div class="byline">
        <b>Agent</b> <time>${formatTime(msg.created_at)}</time>
      </div>
      ${toolRunsHtml}
      <div class="prose">${renderMarkdown(msg.content)}</div>
      ${artifactsHtml}
    </div>
  `;

  // Attach preview listeners
  turnEl.querySelectorAll('.preview-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      previewFile(btn.dataset.path, btn.dataset.name);
    });
  });

  messagesList.appendChild(turnEl);
}

function scrollToBottom() {
  threadContainer.scrollTop = threadContainer.scrollHeight;
}

// --- Send Message ---
async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || !state.currentSessionId) return;

  chatInput.value = '';
  chatInput.style.height = 'auto';
  sendBtn.disabled = true;

  // Optimistically append user turn
  appendMessageToDom({ role: 'user', content: text, created_at: Date.now() / 1000 });
  scrollToBottom();

  // Show working indicator
  const workingEl = document.createElement('div');
  workingEl.className = 'turn';
  workingEl.id = 'workingTurn';
  workingEl.innerHTML = `
    <div class="avatar bot">T</div>
    <div class="body">
      <div class="working">
        <span>Running in isolated workspace</span>
        <div class="dots"><span></span><span></span><span></span></div>
      </div>
    </div>
  `;
  messagesList.appendChild(workingEl);
  scrollToBottom();

  try {
    const outcome = await api('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ session_id: state.currentSessionId, text }),
    });

    const currWorking = document.getElementById('workingTurn');
    if (currWorking) currWorking.remove();

    appendMessageToDom(outcome.message);
    scrollToBottom();

    loadWorkspaceFiles();
    loadSessions();
  } catch (err) {
    const currWorking = document.getElementById('workingTurn');
    if (currWorking) currWorking.remove();

    appendMessageToDom({
      role: 'assistant',
      content: `⚠️ **Execution Error**: ${err.message}`,
      created_at: Date.now() / 1000
    });
    scrollToBottom();
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

// --- Workspace Files Screen ---
async function loadWorkspaceFiles() {
  if (!state.currentSessionId) return;
  try {
    const data = await api(`/api/workspace/${state.currentSessionId}/files`);
    state.workspaceFiles = data.files || [];
    workspaceFilesBadge.textContent = state.workspaceFiles.length;
    renderWorkspaceFilesList();
  } catch (err) {
    console.error('Failed to load workspace files:', err);
  }
}

function renderWorkspaceFilesList() {
  const filter = (fileFilterInput.value || '').toLowerCase().trim();
  const filtered = state.workspaceFiles.filter(f => f.name.toLowerCase().includes(filter));

  if (filtered.length === 0) {
    workspaceFilesList.innerHTML = `<div class="empty">${filter ? 'No files match your filter.' : 'No files generated yet in this session.'}</div>`;
    return;
  }

  workspaceFilesList.innerHTML = filtered.map(f => {
    const ext = f.name.split('.').pop() || 'file';
    const href = `/api/workspace/${state.currentSessionId}/file?path=${encodeURIComponent(f.rel_path)}`;
    return `
      <div class="card" style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 12px; overflow: hidden;">
          <span class="filechip">${ext.toUpperCase()}</span>
          <div>
            <h3 style="margin: 0; font-size: 13.5px;">${escapeHtml(f.name)}</h3>
            <span class="meta">${formatBytes(f.size)}</span>
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn preview-file-btn" data-path="${escapeHtml(f.rel_path)}" data-name="${escapeHtml(f.name)}">View</button>
          <a class="btn btn-primary" href="${href}" download="${escapeHtml(f.name)}">Download</a>
        </div>
      </div>
    `;
  }).join('');

  workspaceFilesList.querySelectorAll('.preview-file-btn').forEach(btn => {
    btn.addEventListener('click', () => previewFile(btn.dataset.path, btn.dataset.name));
  });
}

fileFilterInput.addEventListener('input', renderWorkspaceFilesList);

async function previewFile(relPath, filename) {
  try {
    const resp = await fetch(`/api/workspace/${state.currentSessionId}/file?path=${encodeURIComponent(relPath)}`);
    const content = await resp.text();
    previewFileName.textContent = filename;
    previewFileContent.textContent = content;
    downloadPreviewBtn.href = `/api/workspace/${state.currentSessionId}/file?path=${encodeURIComponent(relPath)}`;
    downloadPreviewBtn.download = filename;
    filePreviewModal.classList.add('open');
  } catch (err) {
    alert('Failed to preview file: ' + err.message);
  }
}

// --- Connectors Screen (Matching your screenshot) ---
async function loadConnectors() {
  try {
    const data = await api('/api/connectors');
    state.connectors = data.connectors || [];
    renderConnectorsList();
  } catch (err) {
    console.error('Failed to load connectors:', err);
  }
}

function renderConnectorsList() {
  connectorsList.innerHTML = '';
  let activeCount = 0;

  state.connectors.forEach(c => {
    if (c.enabled) activeCount++;
    const card = document.createElement('div');
    card.className = 'connector-card';
    card.innerHTML = `
      <div class="connector-info">
        <div class="connector-icon-wrapper">
          ${getConnectorEmoji(c.id)}
        </div>
        <div class="connector-texts">
          <span class="connector-title">${escapeHtml(c.name)}</span>
          <span class="connector-desc">${escapeHtml(c.description)}</span>
        </div>
      </div>
      <button class="btn-connector-toggle ${c.enabled ? 'connected' : ''}" data-id="${c.id}" title="${c.enabled ? 'Connected' : 'Click to connect'}">
        ${c.enabled ? '✓' : '+'}
      </button>
    `;

    card.querySelector('.btn-connector-toggle').addEventListener('click', () => {
      handleConnectorClick(c);
    });

    connectorsList.appendChild(card);
  });

  activeConnectorsBadge.textContent = activeCount;
}

function handleConnectorClick(connector) {
  if (!connector.is_configured && connector.fields && connector.fields.length > 0) {
    configConnectorId.value = connector.id;
    configConnectorName.textContent = `Connect ${connector.name}`;
    configFormFields.innerHTML = connector.fields.map(f => `
      <div class="form-group">
        <label for="field_${f.key}">${escapeHtml(f.label)}</label>
        <input type="${f.type}" id="field_${f.key}" name="${f.key}" required>
      </div>
    `).join('');
    connectorConfigModal.classList.add('open');
  } else {
    toggleConnectorState(connector.id);
  }
}

async function toggleConnectorState(connectorId) {
  try {
    const res = await api(`/api/connectors/${connectorId}/toggle`, { method: 'POST', body: JSON.stringify({}) });
    const c = state.connectors.find(x => x.id === connectorId);
    if (c) c.enabled = res.enabled;
    renderConnectorsList();
  } catch (err) {
    alert('Failed to toggle connector: ' + err.message);
  }
}

// --- Event Listeners ---
burgerBtn.addEventListener('click', () => {
  sidebar.classList.toggle('open');
  scrim.classList.toggle('open');
});
scrim.addEventListener('click', () => {
  sidebar.classList.remove('open');
  scrim.classList.remove('open');
});

navChat.addEventListener('click', () => switchScreen('chat'));
navConnectors.addEventListener('click', () => switchScreen('connectors'));
navFiles.addEventListener('click', () => switchScreen('files'));

newChatBtn.addEventListener('click', createNewSession);
clearAllChatsBtn.addEventListener('click', clearAllChats);

// Input handling
chatInput.addEventListener('input', () => {
  sendBtn.disabled = !chatInput.value.trim();
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 180) + 'px';
});

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) sendMessage();
  }
});

sendBtn.addEventListener('click', sendMessage);

// Connector configuration modal
closeConfigModalBtn.addEventListener('click', () => connectorConfigModal.classList.remove('open'));
cancelConfigBtn.addEventListener('click', () => connectorConfigModal.classList.remove('open'));

connectorConfigForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const cid = configConnectorId.value;
  const formData = new FormData(connectorConfigForm);
  const config = {};
  formData.forEach((val, key) => { config[key] = val; });

  try {
    await api(`/api/connectors/${cid}/config`, {
      method: 'POST',
      body: JSON.stringify({ config }),
    });
    connectorConfigModal.classList.remove('open');
    loadConnectors();
  } catch (err) {
    alert('Failed to save configuration: ' + err.message);
  }
});

// Custom MCP modal
openAddMcpBtn.addEventListener('click', () => addMcpModal.classList.add('open'));
closeAddMcpModalBtn.addEventListener('click', () => addMcpModal.classList.remove('open'));
cancelAddMcpBtn.addEventListener('click', () => addMcpModal.classList.remove('open'));

mcpKind.addEventListener('change', () => {
  if (mcpKind.value === 'mcp_stdio') {
    mcpCommandGroup.classList.remove('hidden');
    mcpUrlGroup.classList.add('hidden');
  } else {
    mcpCommandGroup.classList.add('hidden');
    mcpUrlGroup.classList.remove('hidden');
  }
});

addMcpForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('mcpName').value.trim();
  const kind = mcpKind.value;
  const desc = document.getElementById('mcpDescription').value.trim();
  const config = kind === 'mcp_stdio'
    ? { command: document.getElementById('mcpCommand').value.trim() }
    : { url: document.getElementById('mcpUrl').value.trim() };

  try {
    await api('/api/connectors/custom_mcp', {
      method: 'POST',
      body: JSON.stringify({ name, kind, description: desc, config }),
    });
    addMcpModal.classList.remove('open');
    addMcpForm.reset();
    loadConnectors();
  } catch (err) {
    alert('Failed to add custom MCP server: ' + err.message);
  }
});

closePreviewBtn.addEventListener('click', () => filePreviewModal.classList.remove('open'));

// Theme Picker
themePicker.querySelectorAll('button').forEach(btn => {
  btn.addEventListener('click', () => {
    const val = btn.dataset.themeVal;
    document.documentElement.setAttribute('data-theme', val);
    localStorage.setItem('termux_agent_theme', val);
    themePicker.querySelectorAll('button').forEach(b => {
      b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
    });
  });
});

// Load saved theme
const savedTheme = localStorage.getItem('termux_agent_theme') || 'system';
document.documentElement.setAttribute('data-theme', savedTheme);
themePicker.querySelectorAll('button').forEach(b => {
  b.setAttribute('aria-pressed', b.dataset.themeVal === savedTheme ? 'true' : 'false');
});

// Boot
window.addEventListener('DOMContentLoaded', () => {
  loadSessions();
  loadConnectors();
});
