// Termux Agent Frontend Client Application

const state = {
  currentSessionId: null,
  sessions: [],
  connectors: [],
  workspaceFiles: [],
};

// --- DOM Elements ---
const sidebar = document.getElementById('sidebar');
const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
const closeSidebarBtn = document.getElementById('closeSidebarBtn');
const newChatBtn = document.getElementById('newChatBtn');
const clearAllChatsBtn = document.getElementById('clearAllChatsBtn');
const sessionsList = document.getElementById('sessionsList');
const currentSessionTitle = document.getElementById('currentSessionTitle');
const currentSessionMeta = document.getElementById('currentSessionMeta');
const messagesList = document.getElementById('messagesList');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const chatContainer = document.getElementById('chatContainer');
const workspaceDrawer = document.getElementById('workspaceDrawer');
const toggleWorkspaceBtn = document.getElementById('toggleWorkspaceBtn');
const closeDrawerBtn = document.getElementById('closeDrawerBtn');
const drawerFileList = document.getElementById('drawerFileList');
const workspaceFileCount = document.getElementById('workspaceFileCount');
const activeConnectorsCount = document.getElementById('activeConnectorsCount');

// Modals
const connectorsModal = document.getElementById('connectorsModal');
const openConnectorsBtn = document.getElementById('openConnectorsBtn');
const topConnectorsBtn = document.getElementById('topConnectorsBtn');
const closeConnectorsModalBtn = document.getElementById('closeConnectorsModalBtn');
const connectorsList = document.getElementById('connectorsList');

const connectorConfigModal = document.getElementById('connectorConfigModal');
const closeConfigModalBtn = document.getElementById('closeConfigModalBtn');
const cancelConfigBtn = document.getElementById('cancelConfigBtn');
const connectorConfigForm = document.getElementById('connectorConfigForm');
const configConnectorName = document.getElementById('configConnectorName');
const configConnectorId = document.getElementById('configConnectorId');
const configFormFields = document.getElementById('configFormFields');

const addMcpModal = document.getElementById('addMcpModal');
const openAddMcpBtn = document.getElementById('openAddMcpBtn');
const closeAddMcpModalBtn = document.getElementById('closeAddMcpModalBtn');
const cancelAddMcpBtn = document.getElementById('cancelAddMcpBtn');
const addMcpForm = document.getElementById('addMcpForm');
const mcpKind = document.getElementById('mcpKind');
const mcpCommandGroup = document.getElementById('mcpCommandGroup');
const mcpUrlGroup = document.getElementById('mcpUrlGroup');

const filePreviewModal = document.getElementById('filePreviewModal');
const closePreviewBtn = document.getElementById('closePreviewBtn');
const previewFileName = document.getElementById('previewFileName');
const previewFileContent = document.getElementById('previewFileContent');
const downloadPreviewBtn = document.getElementById('downloadPreviewBtn');

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
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getFileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  if (['py', 'js', 'sh', 'c', 'cpp', 'rs', 'go'].includes(ext)) return '📜';
  if (['json', 'yaml', 'yml', 'toml'].includes(ext)) return '⚙️';
  if (['csv', 'tsv', 'xlsx'].includes(ext)) return '📊';
  if (['pdf'].includes(ext)) return '📕';
  if (['md', 'txt'].includes(ext)) return '📝';
  if (['html', 'css'].includes(ext)) return '🌐';
  if (['png', 'jpg', 'jpeg', 'gif', 'svg'].includes(ext)) return '🖼️';
  return '📄';
}

function getConnectorIconSvg(name) {
  const icons = {
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
    cpu: '🔌',
  };
  return icons[name.toLowerCase()] || '🔌';
}

// Simple Markdown Formatter
function renderMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Code blocks ```code```
  html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
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

// --- API Calls ---

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
    const item = document.createElement('div');
    item.className = `session-item ${session.id === state.currentSessionId ? 'active' : ''}`;
    item.innerHTML = `
      <div class="session-item-content">
        <span class="session-item-title">${escapeHtml(session.title)}</span>
        <span class="session-item-meta">${session.message_count || 0} messages</span>
      </div>
      <button class="session-item-delete" title="Delete conversation" data-id="${session.id}">🗑️</button>
    `;

    item.querySelector('.session-item-content').addEventListener('click', () => {
      selectSession(session.id);
      if (window.innerWidth <= 768) sidebar.classList.remove('open');
    });

    item.querySelector('.session-item-delete').addEventListener('click', (e) => {
      e.stopPropagation();
      deleteSession(session.id);
    });

    sessionsList.appendChild(item);
  });
}

async function selectSession(sessionId) {
  state.currentSessionId = sessionId;
  renderSessionsList();

  try {
    const data = await api(`/api/sessions/${sessionId}`);
    currentSessionTitle.textContent = data.session.title || 'Chat';
    currentSessionMeta.textContent = `ID: ${sessionId.slice(0, 8)} • Isolated /workspace`;
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
      body: JSON.stringify({ title: 'New Chat' }),
    });
    state.sessions.unshift(data.session);
    selectSession(data.session.id);
    chatInput.focus();
  } catch (err) {
    console.error('Failed to create session:', err);
  }
}

async function deleteSession(sessionId) {
  if (!confirm('Are you sure you want to delete this chat and its isolated workspace?')) return;
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
  if (!confirm('Delete ALL chat conversations and workspace files? This cannot be undone.')) return;
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
      <div style="text-align: center; margin: auto; padding: 40px 20px; color: var(--text-muted);">
        <div style="font-size: 40px; margin-bottom: 12px;">⚡</div>
        <h3 style="color: var(--text-primary); margin-bottom: 8px;">Termux Agent Ready</h3>
        <p style="max-width: 440px; margin: 0 auto; font-size: 13.5px; line-height: 1.5;">
          Ask any question, or run any bash command. If you ask for files or scripts, they are created in your isolated session workspace.
        </p>
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
  const msgEl = document.createElement('div');
  msgEl.className = `message ${msg.role}`;

  let toolRunsHtml = '';
  if (msg.tool_calls && Array.isArray(msg.tool_calls)) {
    toolRunsHtml = `
      <div class="tool-runs-container">
        ${msg.tool_calls.map(tc => {
          const detail = tc.detail || {};
          const isTerminal = detail.tool === 'terminal';
          const title = isTerminal ? detail.command : `${detail.tool || tc.name}`;
          const isOk = detail.ok !== false;
          const statusText = isTerminal ? `Exit ${detail.exit_code}` : (isOk ? 'OK' : 'Error');
          const output = isTerminal ? `${detail.stdout || ''}${detail.stderr ? '\n' + detail.stderr : ''}` : JSON.stringify(detail.result, null, 2);

          return `
            <div class="tool-run-card">
              <div class="tool-run-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
                <div class="tool-run-title">
                  <span class="badge-tool">${isTerminal ? '$ bash' : '🔌 connector'}</span>
                  <code>${escapeHtml(title)}</code>
                </div>
                <span class="badge-status ${isOk ? 'success' : 'error'}">${statusText}</span>
              </div>
              <div class="tool-run-body hidden">${escapeHtml(output || 'No output')}</div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  let artifactsHtml = '';
  if (msg.files_generated && Array.isArray(msg.files_generated) && msg.files_generated.length > 0) {
    artifactsHtml = `
      <div class="artifacts-container">
        ${msg.files_generated.map(file => {
          const name = typeof file === 'string' ? file : file.filename;
          const relPath = typeof file === 'string' ? file : file.rel_path;
          const size = file.size_bytes ? formatBytes(file.size_bytes) : '';
          return `
            <div class="artifact-card">
              <div class="artifact-info">
                <span class="artifact-icon">${getFileIcon(name)}</span>
                <div class="artifact-details">
                  <span class="artifact-name">${escapeHtml(name)}</span>
                  ${size ? `<span class="artifact-size">${size}</span>` : ''}
                </div>
              </div>
              <div class="artifact-actions">
                <button class="btn btn-sm btn-outline preview-file-btn" data-path="${escapeHtml(relPath)}" data-name="${escapeHtml(name)}">View</button>
                <a class="btn btn-sm btn-primary" href="/api/workspace/${state.currentSessionId}/file?path=${encodeURIComponent(relPath)}" download="${escapeHtml(name)}">Download</a>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  msgEl.innerHTML = `
    <div class="message-header">
      <span class="message-author ${msg.role}">${msg.role === 'user' ? 'You' : 'Termux Agent'}</span>
    </div>
    ${toolRunsHtml}
    ${artifactsHtml}
    <div class="message-body">${renderMarkdown(msg.content)}</div>
  `;

  // Attach preview click listeners
  msgEl.querySelectorAll('.preview-file-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      previewFile(btn.dataset.path, btn.dataset.name);
    });
  });

  messagesList.appendChild(msgEl);
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

// --- Send Message ---

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || !state.currentSessionId) return;

  chatInput.value = '';
  chatInput.style.height = 'auto';
  sendBtn.disabled = true;

  // Optimistically show user message
  appendMessageToDom({ role: 'user', content: text });
  scrollToBottom();

  // Show thinking indicator
  const loadingEl = document.createElement('div');
  loadingEl.className = 'message assistant';
  loadingEl.id = 'loadingMessage';
  loadingEl.innerHTML = `
    <div class="message-header"><span class="message-author assistant">Termux Agent</span></div>
    <div class="message-body" style="color: var(--text-muted); font-style: italic;">
      ⚡ Executing in isolated sandbox...
    </div>
  `;
  messagesList.appendChild(loadingEl);
  scrollToBottom();

  try {
    const outcome = await api('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ session_id: state.currentSessionId, text }),
    });

    // Remove loading indicator
    const currentLoading = document.getElementById('loadingMessage');
    if (currentLoading) currentLoading.remove();

    // Render returned assistant message
    appendMessageToDom(outcome.message);
    scrollToBottom();

    // Refresh workspace files & session list
    loadWorkspaceFiles();
    loadSessions();
  } catch (err) {
    const currentLoading = document.getElementById('loadingMessage');
    if (currentLoading) currentLoading.remove();

    appendMessageToDom({
      role: 'assistant',
      content: `❌ **Execution Error**: ${err.message}`,
    });
    scrollToBottom();
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

// --- Workspace Files ---

async function loadWorkspaceFiles() {
  if (!state.currentSessionId) return;
  try {
    const data = await api(`/api/workspace/${state.currentSessionId}/files`);
    state.workspaceFiles = data.files || [];
    workspaceFileCount.textContent = state.workspaceFiles.length;

    drawerFileList.innerHTML = '';
    if (state.workspaceFiles.length === 0) {
      drawerFileList.innerHTML = '<p class="drawer-desc">No files generated yet in this session.</p>';
      return;
    }

    state.workspaceFiles.forEach(f => {
      const item = document.createElement('div');
      item.className = 'file-list-item';
      item.innerHTML = `
        <div class="file-item-left">
          <span>${getFileIcon(f.name)}</span>
          <span class="file-item-name" title="${escapeHtml(f.rel_path)}">${escapeHtml(f.name)}</span>
        </div>
        <div style="display: flex; gap: 6px; align-items: center;">
          <span style="font-size: 11px; color: var(--text-muted);">${formatBytes(f.size)}</span>
          <button class="btn btn-sm btn-outline preview-drawer-btn" data-path="${escapeHtml(f.rel_path)}" data-name="${escapeHtml(f.name)}">View</button>
          <a class="btn btn-sm btn-primary" href="/api/workspace/${state.currentSessionId}/file?path=${encodeURIComponent(f.rel_path)}" download="${escapeHtml(f.name)}">↓</a>
        </div>
      `;

      item.querySelector('.preview-drawer-btn').addEventListener('click', () => {
        previewFile(f.rel_path, f.name);
      });

      drawerFileList.appendChild(item);
    });
  } catch (err) {
    console.error('Failed to load workspace files:', err);
  }
}

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

// --- Connectors Modal (Matching User's Screenshot) ---

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
        <div class="connector-icon-wrapper" style="color: ${c.color || '#3b82f6'};">
          ${getConnectorIconSvg(c.id)}
        </div>
        <div class="connector-texts">
          <span class="connector-title">${escapeHtml(c.name)}</span>
          <span class="connector-desc">${escapeHtml(c.description)}</span>
        </div>
      </div>
      <button class="btn-connector-toggle ${c.enabled ? 'connected' : ''}" data-id="${c.id}" title="${c.enabled ? 'Enabled (click to disable)' : 'Click to connect'}">
        ${c.enabled ? '✓' : '+'}
      </button>
    `;

    const toggleBtn = card.querySelector('.btn-connector-toggle');
    toggleBtn.addEventListener('click', () => {
      handleConnectorClick(c);
    });

    connectorsList.appendChild(card);
  });

  activeConnectorsCount.textContent = activeCount;
}

function handleConnectorClick(connector) {
  if (!connector.is_configured && connector.fields && connector.fields.length > 0) {
    // Open credentials modal
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
    // Toggle on/off directly
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

toggleSidebarBtn.addEventListener('click', () => sidebar.classList.toggle('open'));
closeSidebarBtn.addEventListener('click', () => sidebar.classList.remove('open'));
newChatBtn.addEventListener('click', createNewSession);
clearAllChatsBtn.addEventListener('click', clearAllChats);

toggleWorkspaceBtn.addEventListener('click', () => workspaceDrawer.classList.toggle('open'));
closeDrawerBtn.addEventListener('click', () => workspaceDrawer.classList.remove('open'));

// Connectors modal triggers
openConnectorsBtn.addEventListener('click', () => { loadConnectors(); connectorsModal.classList.add('open'); });
topConnectorsBtn.addEventListener('click', () => { loadConnectors(); connectorsModal.classList.add('open'); });
closeConnectorsModalBtn.addEventListener('click', () => connectorsModal.classList.remove('open'));

// Connector config modal
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
    alert('Failed to save config: ' + err.message);
  }
});

// Custom MCP Modal triggers
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

// Chat Input auto-resize and Enter key
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 180) + 'px';
});

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener('click', sendMessage);

// Initialize Application
window.addEventListener('DOMContentLoaded', () => {
  loadSessions();
  loadConnectors();
});
