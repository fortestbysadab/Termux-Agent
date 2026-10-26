// Termux Agent — Comprehensive Frontend with Arena Workspace Box, Border Beam, Thinking Orb & Bot Avatars

const state = {
  currentSessionId: null,
  activeScreen: 'chat',
  sessions: [],
  connectors: [],
  workspaceFiles: [],
  workspacePanelOpen: false,
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

// Workspace Panel DOM (Arena Style)
const toggleWorkspaceBoxBtn = document.getElementById('toggleWorkspaceBoxBtn');
const topbarWorkspaceCount = document.getElementById('topbarWorkspaceCount');
const workspacePanel = document.getElementById('workspacePanel');
const workspaceScrim = document.getElementById('workspaceScrim');
const closeWorkspacePanelBtn = document.getElementById('closeWorkspacePanelBtn');
const downloadWorkspaceZipBtn = document.getElementById('downloadWorkspaceZipBtn');
const workspaceQuotaText = document.getElementById('workspaceQuotaText');
const workspaceBoxFileCount = document.getElementById('workspaceBoxFileCount');
const workspaceBoxFileList = document.getElementById('workspaceBoxFileList');

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

// Rich Preview Modal
const filePreviewModal = document.getElementById('filePreviewModal');
const previewFileName = document.getElementById('previewFileName');
const previewSpreadsheetContainer = document.getElementById('previewSpreadsheetContainer');
const previewPdfContainer = document.getElementById('previewPdfContainer');
const previewMediaContainer = document.getElementById('previewMediaContainer');
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

// ==============================================================================
// 1. Bot Avatars (libraries.dev/bots) — 2D Canvas Lit Cute Bot Avatar
// ==============================================================================
class BotAvatar {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.size = options.size || 64;
    this.state = options.state || 'default'; // 'default', 'working', 'sleeping'
    this.type = options.type || 'droid';
    this.pointer = { x: 32, y: 32 };
    this.target = { x: 32, y: 32 };
    this.blinkProgress = 0;
    this.hopPhase = 0;
    this.animId = null;

    this.bindEvents();
    this.loop = this.loop.bind(this);
    this.loop();
  }

  bindEvents() {
    window.addEventListener('pointermove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = (e.clientX - cx) / Math.max(window.innerWidth, 1);
      const dy = (e.clientY - cy) / Math.max(window.innerHeight, 1);
      this.target.x = 32 + Math.max(-10, Math.min(10, dx * 30));
      this.target.y = 32 + Math.max(-8, Math.min(8, dy * 25));
    });

    this.canvas.addEventListener('click', () => {
      this.hopPhase = Math.PI * 2;
    });

    setInterval(() => {
      if (this.state !== 'sleeping' && Math.random() > 0.4) {
        this.blinkProgress = 1;
      }
    }, 4500);
  }

  setState(newState) {
    this.state = newState;
  }

  loop() {
    this.update();
    this.render();
    this.animId = requestAnimationFrame(this.loop);
  }

  update() {
    // Easing toward pointer
    this.pointer.x += (this.target.x - this.pointer.x) * 0.12;
    this.pointer.y += (this.target.y - this.pointer.y) * 0.12;

    if (this.blinkProgress > 0) {
      this.blinkProgress = Math.max(0, this.blinkProgress - 0.14);
    }

    if (this.state === 'working') {
      this.hopPhase += 0.15;
    } else if (this.hopPhase > 0) {
      this.hopPhase = Math.max(0, this.hopPhase - 0.1);
    }
  }

  render() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);

    const hopY = Math.sin(this.hopPhase) * (this.state === 'working' ? 4 : 6);
    const centerX = 32;
    const centerY = 32 - hopY;

    // Body: Rounded soft metallic head
    ctx.save();
    ctx.translate(centerX, centerY);

    const grad = ctx.createRadialGradient(-6, -10, 4, 0, 0, 24);
    grad.addColorStop(0, '#a78bfa');
    grad.addColorStop(0.5, '#7c3aed');
    grad.addColorStop(1, '#5b21b6');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.roundRect(-22, -22, 44, 44, 16);
    ctx.fill();

    // Subtle specular sheen
    const sheen = ctx.createLinearGradient(-18, -20, 18, 0);
    sheen.addColorStop(0, 'rgba(255, 255, 255, 0.45)');
    sheen.addColorStop(0.5, 'rgba(255, 255, 255, 0.1)');
    sheen.addColorStop(1, 'transparent');
    ctx.fillStyle = sheen;
    ctx.beginPath();
    ctx.roundRect(-20, -20, 40, 18, 12);
    ctx.fill();

    // Antenna
    ctx.strokeStyle = '#c4b5fd';
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(0, -22);
    ctx.lineTo(0, -27);
    ctx.stroke();

    // Antenna bulb
    ctx.fillStyle = this.state === 'working' ? '#38bdf8' : '#ec4899';
    ctx.beginPath();
    ctx.arc(0, -28, 3.5, 0, Math.PI * 2);
    ctx.fill();

    // Face Screen
    ctx.fillStyle = '#1e1b4b';
    ctx.beginPath();
    ctx.roundRect(-16, -11, 32, 22, 8);
    ctx.fill();

    // Eyes
    const eyeOffsetX = (this.pointer.x - 32) * 0.25;
    const eyeOffsetY = (this.pointer.y - 32) * 0.25;
    const eyeY = 0 + eyeOffsetY;

    if (this.state === 'sleeping' || this.blinkProgress > 0.5) {
      // Curved sleeping/blinking line
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(-7 + eyeOffsetX, eyeY, 3, 0.2, Math.PI - 0.2);
      ctx.arc(7 + eyeOffsetX, eyeY, 3, 0.2, Math.PI - 0.2);
      ctx.stroke();
    } else {
      // Glossy bead eyes
      ctx.fillStyle = '#38bdf8';
      ctx.beginPath();
      ctx.arc(-7 + eyeOffsetX, eyeY, 3.5, 0, Math.PI * 2);
      ctx.arc(7 + eyeOffsetX, eyeY, 3.5, 0, Math.PI * 2);
      ctx.fill();

      // Pupil gleam
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(-8 + eyeOffsetX, eyeY - 1, 1.2, 0, Math.PI * 2);
      ctx.arc(6 + eyeOffsetX, eyeY - 1, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }
}

// Instantiate Brand Avatar in Sidebar
const brandAvatarCanvas = document.getElementById('brandBotAvatar');
let globalBotAvatar = null;
if (brandAvatarCanvas) {
  globalBotAvatar = new BotAvatar(brandAvatarCanvas, { size: 32 });
}

// ==============================================================================
// 2. Thinking Orb (libraries.dev/orbs) — Fluid Organic Multi-layered Thinking Orb
// ==============================================================================
function createThinkingOrb(size = 22, state = 'working') {
  const canvas = document.createElement('canvas');
  canvas.width = size * 2;
  canvas.height = size * 2;
  canvas.style.width = size + 'px';
  canvas.style.height = size + 'px';
  canvas.className = 'thinking-orb-canvas';

  const ctx = canvas.getContext('2d');
  let angle = 0;
  let animId = null;

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const cx = size;
    const cy = size;
    angle += 0.05;

    // Layer 1: Glowing Outer Halo
    const halo = ctx.createRadialGradient(cx, cy, size * 0.2, cx, cy, size * 0.95);
    halo.addColorStop(0, 'rgba(124, 58, 237, 0.6)');
    halo.addColorStop(0.5, 'rgba(56, 189, 248, 0.35)');
    halo.addColorStop(1, 'rgba(124, 58, 237, 0)');
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(cx, cy, size * 0.95, 0, Math.PI * 2);
    ctx.fill();

    // Layer 2: Rotating Liquid Orbital Core
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(angle);

    const coreGrad = ctx.createLinearGradient(-size * 0.5, -size * 0.5, size * 0.5, size * 0.5);
    if (state === 'searching') {
      coreGrad.addColorStop(0, '#06b6d4');
      coreGrad.addColorStop(1, '#3b82f6');
    } else if (state === 'solving') {
      coreGrad.addColorStop(0, '#f59e0b');
      coreGrad.addColorStop(1, '#ec4899');
    } else {
      coreGrad.addColorStop(0, '#7c3aed');
      coreGrad.addColorStop(1, '#38bdf8');
    }

    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(0, 0, size * 0.5 + Math.sin(angle * 2) * (size * 0.08), 0, Math.PI * 2);
    ctx.fill();

    // Little satellite spark
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(Math.cos(angle * 3) * (size * 0.6), Math.sin(angle * 3) * (size * 0.6), size * 0.12, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();

    animId = requestAnimationFrame(draw);
  }

  draw();
  return { el: canvas, stop: () => cancelAnimationFrame(animId) };
}

// ==============================================================================
// 3. Screen Switching & Navigation
// ==============================================================================
function switchScreen(screen) {
  state.activeScreen = screen;

  navChat.classList.toggle('active', screen === 'chat');
  navChat.setAttribute('aria-current', screen === 'chat' ? 'page' : 'false');
  navConnectors.classList.toggle('active', screen === 'connectors');
  navConnectors.setAttribute('aria-current', screen === 'connectors' ? 'page' : 'false');
  navFiles.classList.toggle('active', screen === 'files');
  navFiles.setAttribute('aria-current', screen === 'files' ? 'page' : 'false');

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

  sidebar.classList.remove('open');
  scrim.classList.remove('open');
}

// ==============================================================================
// 4. Arena-Style Workspace Box Panel Logic
// ==============================================================================
function toggleWorkspacePanel(forceOpen = null) {
  state.workspacePanelOpen = forceOpen !== null ? forceOpen : !state.workspacePanelOpen;
  workspacePanel.classList.toggle('open', state.workspacePanelOpen);
  workspaceScrim.classList.toggle('open', state.workspacePanelOpen && window.innerWidth <= 900);
  toggleWorkspaceBoxBtn.classList.toggle('open', state.workspacePanelOpen);

  if (state.workspacePanelOpen) {
    loadWorkspaceFiles();
  }
}

toggleWorkspaceBoxBtn.addEventListener('click', () => toggleWorkspacePanel());
closeWorkspacePanelBtn.addEventListener('click', () => toggleWorkspacePanel(false));
workspaceScrim.addEventListener('click', () => toggleWorkspacePanel(false));

function updateWorkspacePanelUI() {
  const count = state.workspaceFiles.length;
  topbarWorkspaceCount.textContent = count;
  workspaceBoxFileCount.textContent = count;
  workspaceFilesBadge.textContent = count;

  // Calculate total size
  const totalBytes = state.workspaceFiles.reduce((acc, f) => acc + (f.size || 0), 0);
  workspaceQuotaText.textContent = `${formatBytes(totalBytes)} / 128.0 MB · ${count} file${count === 1 ? '' : 's'}`;

  // Configure ZIP download URL
  if (state.currentSessionId) {
    downloadWorkspaceZipBtn.href = `/api/workspace/${state.currentSessionId}/zip`;
    downloadWorkspaceZipBtn.download = `workspace_${state.currentSessionId.slice(0, 8)}.zip`;
  }

  // Render workspace tree list
  if (state.workspaceFiles.length === 0) {
    workspaceBoxFileList.innerHTML = `
      <div style="padding: 24px 12px; color: var(--muted); font-size: 12.5px; text-align: center;">
        No files in session workspace.
      </div>
    `;
    return;
  }

  workspaceBoxFileList.innerHTML = state.workspaceFiles.map(f => {
    const ext = f.name.split('.').pop() || 'file';
    const href = `/api/workspace/${state.currentSessionId}/file?path=${encodeURIComponent(f.rel_path)}`;
    return `
      <div class="workspace-tree-item">
        <div class="workspace-tree-info">
          <span class="filechip">${ext.toUpperCase()}</span>
          <div>
            <div class="workspace-tree-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</div>
            <div class="workspace-tree-size">${formatBytes(f.size)}</div>
          </div>
        </div>
        <div class="workspace-tree-actions">
          <button class="workspace-tree-btn preview-btn" data-path="${escapeHtml(f.rel_path)}" data-name="${escapeHtml(f.name)}">View</button>
          <a class="workspace-tree-btn" href="${href}" download="${escapeHtml(f.name)}">⬇</a>
        </div>
      </div>
    `;
  }).join('');

  workspaceBoxFileList.querySelectorAll('.preview-btn').forEach(btn => {
    btn.addEventListener('click', () => previewFile(btn.dataset.path, btn.dataset.name));
  });
}

// ==============================================================================
// 5. Sessions Management
// ==============================================================================
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

// ==============================================================================
// 6. Messages & Chat Rendering
// ==============================================================================
function renderMessages(messages) {
  messagesList.innerHTML = '';
  if (messages.length === 0) {
    messagesList.innerHTML = `
      <div class="empty" style="text-align: center; padding: 48px 16px; color: var(--muted);">
        <div style="font-size: 32px; margin-block-end: 8px;">⚡</div>
        <b style="color: var(--fg); font-size: 15px;">Termux Agent is ready.</b><br>
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
          <div class="filepreview" style="padding: 12px 14px; background: var(--soft-bg); font-size: 12px; white-space: pre-wrap; max-height: 250px; overflow-y: auto;">${escapeHtml(output || 'No output')}</div>
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
    <div class="avatar bot"><canvas class="bot-turn-avatar" width="64" height="64" style="width: 100%; height: 100%; display: block;"></canvas></div>
    <div class="body">
      <div class="byline">
        <b>Agent</b> <time>${formatTime(msg.created_at)}</time>
      </div>
      ${toolRunsHtml}
      <div class="prose">${renderMarkdown(msg.content)}</div>
      ${artifactsHtml}
    </div>
  `;

  // Attach avatar renderer
  const avatarCanvas = turnEl.querySelector('.bot-turn-avatar');
  if (avatarCanvas) {
    new BotAvatar(avatarCanvas, { size: 32, state: 'default' });
  }

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

// ==============================================================================
// 7. Real-Time Streaming Send Message with Border Beam & Thinking Orb
// ==============================================================================
async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || !state.currentSessionId) return;

  chatInput.value = '';
  chatInput.style.height = 'auto';
  sendBtn.disabled = true;

  if (globalBotAvatar) globalBotAvatar.setState('working');

  // 1. Append user turn
  appendMessageToDom({ role: 'user', content: text, created_at: Date.now() / 1000 });
  scrollToBottom();

  // 2. Create in-flight Assistant turn with Border Beam container
  const assistantTurn = document.createElement('div');
  assistantTurn.className = 'turn border-beam-container';
  assistantTurn.id = 'liveAssistantTurn';
  assistantTurn.innerHTML = `
    <div class="border-beam variant-colorful"></div>
    <div class="avatar bot"><canvas id="liveBotAvatar" width="64" height="64" style="width: 100%; height: 100%; display: block;"></canvas></div>
    <div class="body">
      <div class="byline"><b>Agent</b> <time>${formatTime(Date.now() / 1000)}</time></div>
      <div id="liveToolRuns" style="display: flex; flex-direction: column; gap: 8px;"></div>
      <div id="liveStatus" class="working" style="margin-block: 8px 12px; display: flex; align-items: center; gap: 10px;">
        <div id="liveOrbContainer" style="display: inline-flex;"></div>
        <span id="liveStatusText">Thinking...</span>
      </div>
      <div class="prose" id="liveProse"></div>
      <div id="liveArtifacts"></div>
    </div>
  `;
  messagesList.appendChild(assistantTurn);
  scrollToBottom();

  // Instantiate live avatar and Thinking Orb
  const liveAvatarCanvas = document.getElementById('liveBotAvatar');
  const liveAvatar = liveAvatarCanvas ? new BotAvatar(liveAvatarCanvas, { size: 32, state: 'working' }) : null;
  const liveOrbContainer = document.getElementById('liveOrbContainer');
  let activeOrb = null;
  if (liveOrbContainer) {
    activeOrb = createThinkingOrb(22, 'searching');
    liveOrbContainer.appendChild(activeOrb.el);
  }

  const liveToolRuns = document.getElementById('liveToolRuns');
  const liveStatus = document.getElementById('liveStatus');
  const liveStatusText = document.getElementById('liveStatusText');
  const liveProse = document.getElementById('liveProse');
  const liveArtifacts = document.getElementById('liveArtifacts');

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: state.currentSessionId, text, stream: true }),
    });

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const blocks = buffer.split('\n\n');
      buffer = blocks.pop();

      for (const block of blocks) {
        if (!block.trim()) continue;
        let eventType = 'message';
        let dataStr = '';

        for (const line of block.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            dataStr = line.slice(6).trim();
          }
        }

        if (!dataStr) continue;
        let data;
        try { data = JSON.parse(dataStr); } catch { continue; }

        if (eventType === 'status') {
          if (liveStatusText) liveStatusText.textContent = data.message;
          scrollToBottom();
        } else if (eventType === 'command_start') {
          // Display EXACT BASH command running live
          if (liveStatus) {
            liveStatus.innerHTML = `
              <div id="liveOrbContainer" style="display: inline-flex;"></div>
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span class="filechip" style="background: var(--accent-soft); color: var(--accent);">$ BASH</span>
                <code style="font-weight: 600; font-size: 13px; color: var(--fg); background: var(--soft-bg); padding: 3px 8px; border-radius: 6px;">${escapeHtml(data.command)}</code>
              </div>
            `;
            const orbBox = document.getElementById('liveOrbContainer');
            if (orbBox) {
              if (activeOrb) activeOrb.stop();
              activeOrb = createThinkingOrb(22, 'working');
              orbBox.appendChild(activeOrb.el);
            }
          }
          scrollToBottom();
        } else if (eventType === 'command_done') {
          const isOk = data.ok !== false;
          const statusBadge = `Exit ${data.exit_code}`;
          const output = `${data.stdout || ''}${data.stderr ? '\n' + data.stderr : ''}`;

          const card = document.createElement('div');
          card.className = 'filecard';
          card.style.fontFamily = 'ui-monospace, Menlo, Consolas, monospace';
          card.innerHTML = `
            <div class="filecard-head" style="cursor: pointer;">
              <span class="filechip" style="background: ${isOk ? 'var(--accent-soft)' : 'color-mix(in srgb, var(--danger) 15%, transparent)'}; color: ${isOk ? 'var(--accent)' : 'var(--danger)'};">
                $ BASH
              </span>
              <span class="filename" style="font-weight: 550;">${escapeHtml(data.command)}</span>
              <span class="opens" style="color: ${isOk ? 'var(--ok)' : 'var(--danger)'}; font-size: 11px;">
                ${statusBadge} ▾
              </span>
            </div>
            <div class="filepreview" style="padding: 12px 14px; background: var(--soft-bg); font-size: 12px; white-space: pre-wrap; max-height: 250px; overflow-y: auto;">${escapeHtml(output || 'No output')}</div>
          `;
          card.querySelector('.filecard-head').addEventListener('click', () => {
            card.querySelector('.filepreview').classList.toggle('hidden');
          });

          if (liveToolRuns) liveToolRuns.appendChild(card);
          if (liveStatus) {
            liveStatus.innerHTML = `
              <div id="liveOrbContainer" style="display: inline-flex;"></div>
              <span>Processing command results...</span>
            `;
            const orbBox = document.getElementById('liveOrbContainer');
            if (orbBox) {
              if (activeOrb) activeOrb.stop();
              activeOrb = createThinkingOrb(22, 'solving');
              orbBox.appendChild(activeOrb.el);
            }
          }
          scrollToBottom();
        } else if (eventType === 'connector_start') {
          if (liveStatus) {
            liveStatus.innerHTML = `
              <div id="liveOrbContainer" style="display: inline-flex;"></div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="filechip" style="background: var(--accent-soft); color: var(--accent);">🔌 MCP</span>
                <b>${escapeHtml(data.tool)}</b>
              </div>
            `;
          }
          scrollToBottom();
        } else if (eventType === 'connector_done') {
          const isOk = data.ok !== false;
          const card = document.createElement('div');
          card.className = 'filecard';
          card.innerHTML = `
            <div class="filecard-head" style="cursor: pointer;">
              <span class="filechip">🔌 MCP</span>
              <span class="filename">${escapeHtml(data.tool)}</span>
              <span class="opens" style="color: ${isOk ? 'var(--ok)' : 'var(--danger)'}; font-size: 11px;">
                ${isOk ? 'OK' : 'Error'} ▾
              </span>
            </div>
            <div class="filepreview hidden" style="padding: 12px 14px; background: var(--soft-bg); font-size: 12px; white-space: pre-wrap;">${escapeHtml(JSON.stringify(data.result, null, 2))}</div>
          `;
          card.querySelector('.filecard-head').addEventListener('click', () => {
            card.querySelector('.filepreview').classList.toggle('hidden');
          });
          if (liveToolRuns) liveToolRuns.appendChild(card);
          scrollToBottom();
        } else if (eventType === 'error') {
          if (liveStatus) liveStatus.remove();
          if (activeOrb) activeOrb.stop();
          const errCard = document.createElement('div');
          errCard.className = 'filecard';
          errCard.style.borderColor = 'var(--danger)';
          errCard.style.background = 'color-mix(in srgb, var(--danger) 8%, var(--surface))';
          errCard.innerHTML = `
            <div style="padding: 14px 16px;">
              <div style="display: flex; align-items: center; gap: 8px; color: var(--danger); font-weight: 650; margin-block-end: 6px;">
                <span>⚠️</span> <span>${escapeHtml(data.title || 'Error')}</span>
              </div>
              <div style="font-size: 13.5px; line-height: 1.5; color: var(--fg);">${escapeHtml(data.message)}</div>
              ${data.remedy ? `<div style="font-size: 12.5px; color: var(--muted); margin-block-start: 8px;"><b>Fix:</b> ${escapeHtml(data.remedy)}</div>` : ''}
              ${data.raw ? `
                <details style="margin-block-start: 10px; font-size: 11px;">
                  <summary style="cursor: pointer; color: var(--muted);">View raw details</summary>
                  <pre style="margin-block-start: 6px; padding: 8px; background: var(--soft-bg); border-radius: 6px; overflow-x: auto;">${escapeHtml(data.raw)}</pre>
                </details>
              ` : ''}
            </div>
          `;
          if (liveProse) liveProse.appendChild(errCard);
          scrollToBottom();
        } else if (eventType === 'done') {
          if (liveStatus) liveStatus.remove();
          if (activeOrb) activeOrb.stop();

          // Remove border beam from turn now that work is complete
          const beam = assistantTurn.querySelector('.border-beam');
          if (beam) beam.remove();
          assistantTurn.classList.remove('border-beam-container');

          if (liveAvatar) liveAvatar.setState('default');
          if (globalBotAvatar) globalBotAvatar.setState('default');

          const msg = data.message || {};
          if (liveProse) liveProse.innerHTML = renderMarkdown(msg.content);

          if (data.files_generated && data.files_generated.length > 0 && liveArtifacts) {
            liveArtifacts.innerHTML = data.files_generated.map(file => {
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

            liveArtifacts.querySelectorAll('.preview-btn').forEach(btn => {
              btn.addEventListener('click', () => previewFile(btn.dataset.path, btn.dataset.name));
            });
          }

          assistantTurn.removeAttribute('id');
          scrollToBottom();
          loadWorkspaceFiles();
          loadSessions();
        }
      }
    }
  } catch (err) {
    if (liveStatus) liveStatus.remove();
    if (activeOrb) activeOrb.stop();
    if (liveProse) {
      liveProse.innerHTML = `
        <div class="filecard" style="border-color: var(--danger); background: color-mix(in srgb, var(--danger) 8%, var(--surface)); padding: 14px 16px;">
          <div style="color: var(--danger); font-weight: 600; margin-block-end: 4px;">⚠️ Request Error</div>
          <div style="font-size: 13.5px;">${escapeHtml(err.message)}</div>
        </div>
      `;
    }
    scrollToBottom();
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
    if (globalBotAvatar) globalBotAvatar.setState('default');
  }
}

// ==============================================================================
// 8. Workspace Files Screen & Rich Previewers (PDF, Spreadsheets, Media, Code)
// ==============================================================================
async function loadWorkspaceFiles() {
  if (!state.currentSessionId) return;
  try {
    const data = await api(`/api/workspace/${state.currentSessionId}/files`);
    state.workspaceFiles = data.files || [];
    updateWorkspacePanelUI();
    renderWorkspaceFilesList();
  } catch (err) {
    console.error('Failed to load workspace files:', err);
  }
}

function renderWorkspaceFilesList() {
  const filter = (fileFilterInput.value || '').toLowerCase().trim();
  const filtered = state.workspaceFiles.filter(f => f.name.toLowerCase().includes(filter));

  if (filtered.length === 0) {
    workspaceFilesList.innerHTML = `<div class="empty" style="text-align: center; padding: 32px; color: var(--muted);">${filter ? 'No files match your filter.' : 'No files generated yet in this session.'}</div>`;
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
            <span class="meta" style="font-size: 11px; color: var(--muted);">${formatBytes(f.size)}</span>
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

// Rich File Preview Modal (Handles PDF, Spreadsheets, Images, Code)
async function previewFile(relPath, filename) {
  const fileUrl = `/api/workspace/${state.currentSessionId}/file?path=${encodeURIComponent(relPath)}`;
  const previewUrl = `/api/workspace/${state.currentSessionId}/preview?path=${encodeURIComponent(relPath)}`;

  previewFileName.textContent = filename;
  downloadPreviewBtn.href = fileUrl;
  downloadPreviewBtn.download = filename;

  // Reset all containers
  previewSpreadsheetContainer.style.display = 'none';
  previewSpreadsheetContainer.innerHTML = '';
  previewPdfContainer.style.display = 'none';
  previewPdfContainer.innerHTML = '';
  previewMediaContainer.style.display = 'none';
  previewMediaContainer.innerHTML = '';
  previewFileContent.style.display = 'none';
  previewFileContent.textContent = '';

  filePreviewModal.classList.add('open');

  try {
    const resp = await fetch(previewUrl);
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
    }
    const data = await resp.json();

    if (data.type === 'spreadsheet' && data.sheets && data.sheets.length > 0) {
      // 1. Spreadsheet (XLSX / CSV) Viewer
      const sheet = data.sheets[0];
      const rows = sheet.rows || [];

      if (rows.length === 0) {
        previewSpreadsheetContainer.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--muted);">Spreadsheet is empty.</div>';
      } else {
        const headerRow = rows[0] || [];
        const bodyRows = rows.slice(1);

        let tableHtml = `
          <div style="margin-bottom: 8px; font-weight: 600; font-size: 13px; color: var(--fg-soft);">
            Sheet: <span>${escapeHtml(sheet.name)}</span> (${rows.length} rows)
          </div>
          <div class="spreadsheet-wrap">
            <table class="spreadsheet-table">
              <thead>
                <tr>
                  ${headerRow.map(h => `<th>${escapeHtml(h)}</th>`).join('')}
                </tr>
              </thead>
              <tbody>
                ${bodyRows.map(r => `
                  <tr>
                    ${r.map(c => `<td>${escapeHtml(c)}</td>`).join('')}
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
        previewSpreadsheetContainer.innerHTML = tableHtml;
      }
      previewSpreadsheetContainer.style.display = 'block';

    } else if (data.type === 'pdf') {
      // 2. Rich PDF Viewer (Works flawlessly on mobile & desktop)
      previewPdfContainer.innerHTML = `
        <div class="pdf-preview-card">
          <div class="pdf-icon-big">📄</div>
          <div class="pdf-title">${escapeHtml(filename)}</div>
          <div class="pdf-meta">Portable Document Format · ${formatBytes(data.size)}</div>
          <div class="pdf-actions">
            <a class="btn btn-primary" href="${fileUrl}" target="_blank" rel="noopener">Open in PDF Viewer</a>
            <a class="btn" href="${fileUrl}" download="${escapeHtml(filename)}">Download PDF</a>
          </div>
          <iframe src="${fileUrl}" style="width: 100%; height: 50vh; border: 1px solid var(--border); border-radius: 8px; margin-top: 10px; background: #fff;"></iframe>
        </div>
      `;
      previewPdfContainer.style.display = 'block';

    } else if (data.type === 'image') {
      // 3. Image Viewer
      previewMediaContainer.innerHTML = `
        <img src="${fileUrl}" alt="${escapeHtml(filename)}" style="max-width: 100%; max-height: 60vh; object-fit: contain; border-radius: 8px; box-shadow: 0 4px 14px rgb(0 0 0 / 10%);">
      `;
      previewMediaContainer.style.display = 'block';

    } else {
      // 4. Code / Text Viewer
      previewFileContent.textContent = data.content || '';
      previewFileContent.style.display = 'block';
    }

  } catch (err) {
    // Fallback: fetch raw text
    try {
      const rawResp = await fetch(fileUrl);
      const rawText = await rawResp.text();
      previewFileContent.textContent = rawText;
      previewFileContent.style.display = 'block';
    } catch (e) {
      previewFileContent.textContent = `Error loading file preview: ${err.message}`;
      previewFileContent.style.display = 'block';
    }
  }
}

closePreviewBtn.addEventListener('click', () => filePreviewModal.classList.remove('open'));

// ==============================================================================
// 9. Connectors Screen
// ==============================================================================
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

// ==============================================================================
// 10. Event Listeners & Boot
// ==============================================================================
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
