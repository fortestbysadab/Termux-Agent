/**
 * Thin client for the Termux Agent HTTP API.
 * The server is standard-library `http.server`; every route returns JSON
 * except the file/zip endpoints and the SSE stream on POST /api/chat.
 */

export async function api(path, options = {}) {
  const resp = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    let message = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      message = body.error || message;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(message);
  }
  return resp.json();
}

export const getSessions = () => api('/api/sessions').then((d) => d.sessions || []);
export const getSession = (id) => api(`/api/sessions/${id}`);
export const createSession = (title = 'New chat') =>
  api('/api/sessions', { method: 'POST', body: JSON.stringify({ title }) }).then((d) => d.session);
export const deleteSession = (id) => api(`/api/sessions/${id}`, { method: 'DELETE' });
export const clearSessions = () => api('/api/sessions', { method: 'DELETE' });

export const getConnectors = () => api('/api/connectors').then((d) => d.connectors || []);
export const toggleConnector = (id, enabled) =>
  api(`/api/connectors/${id}/toggle`, { method: 'POST', body: JSON.stringify({ enabled }) });
export const saveConnectorConfig = (id, payload) =>
  api(`/api/connectors/${id}/config`, { method: 'POST', body: JSON.stringify(payload) });
export const addCustomMcp = (payload) =>
  api('/api/connectors/custom_mcp', { method: 'POST', body: JSON.stringify(payload) });
export const removeConnector = (id) => api(`/api/connectors/${id}`, { method: 'DELETE' });

export const getConfig = () => api('/api/config');
export const getEnvironment = () => api('/api/environment');
export const getSkills = () => api('/api/skills').then((d) => d.skills || []);
export const toggleSkill = (name, enabled) =>
  api(`/api/skills/${name}/toggle`, { method: 'POST', body: JSON.stringify({ enabled }) });

/**
 * Uploads go to <workspace>/uploads. Uses XHR rather than fetch because it is
 * the only way to report upload progress on Safari.
 */
export function uploadFiles(sessionId, files, onProgress) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const file of files) form.append('file', file, file.name);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/workspace/${sessionId}/upload`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded / e.total);
    };
    xhr.onload = () => {
      let payload = {};
      try {
        payload = JSON.parse(xhr.responseText || '{}');
      } catch {
        /* non-JSON body */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(payload.files || []);
      else reject(new Error(payload.error || `Upload failed (HTTP ${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error('Network error during upload'));
    xhr.send(form);
  });
}

export const getWorkspaceFiles = (sessionId) =>
  api(`/api/workspace/${sessionId}/files`).then((d) => d.files || []);
export const getPreview = (sessionId, relPath) =>
  api(`/api/workspace/${sessionId}/preview?path=${encodeURIComponent(relPath)}`);

export const fileUrl = (sessionId, relPath) =>
  `/api/workspace/${sessionId}/file?path=${encodeURIComponent(relPath)}`;
export const zipUrl = (sessionId) => `/api/workspace/${sessionId}/zip`;

/**
 * Streams one agent turn. Calls onEvent(type, payload) for each SSE frame:
 *   status | command_start | command_done | connector_start | connector_done | error | done
 * Note the server answers a POST with `text/event-stream`, so we can't use
 * EventSource — we read the body stream and parse the frames ourselves.
 */
export async function streamChat({
  sessionId,
  text,
  attachments = [],
  inputResponses = null,
  requestState = null,
  onEvent,
  signal,
}) {
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      text,
      stream: true,
      attachments,
      input_responses: inputResponses,
      request_state: requestState,
    }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`The agent endpoint returned HTTP ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const handleBlock = (block) => {
    if (!block.trim()) return;
    let type = 'message';
    let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) type = line.slice(7).trim();
      else if (line.startsWith('data: ')) data += line.slice(6);
    }
    if (!data) return;
    try {
      onEvent(type, JSON.parse(data));
    } catch {
      /* ignore a malformed frame */
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() ?? '';

    for (const block of blocks) {
      handleBlock(block);
    }
  }

  // A stream that ends without a trailing blank line would otherwise lose its
  // last frame — which is usually `done`. Flush whatever is left.
  handleBlock(buffer);

}

/* ---------------------------------------------------------------- skills */
export const createSkill = (payload) =>
  api('/api/skills', { method: 'POST', body: JSON.stringify(payload) }).then((d) => d.skill);

export const updateSkill = (name, payload) =>
  api(`/api/skills/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }).then((d) => d.skill);

export const deleteSkill = (name) =>
  api(`/api/skills/${encodeURIComponent(name)}`, { method: 'DELETE' });

/** What would the router load for this sentence? */
export const routeSkills = (query, files = []) => {
  const params = new URLSearchParams({ q: query });
  files.forEach((f) => params.append('file', f));
  return api(`/api/skills/router?${params.toString()}`).then((d) => d.matches || []);
};
