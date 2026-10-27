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
export async function streamChat({ sessionId, text, onEvent, signal }) {
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, text, stream: true }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`The agent endpoint returned HTTP ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() ?? '';

    for (const block of blocks) {
      if (!block.trim()) continue;
      let type = 'message';
      let data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) type = line.slice(7).trim();
        else if (line.startsWith('data: ')) data += line.slice(6);
      }
      if (!data) continue;
      try {
        onEvent(type, JSON.parse(data));
      } catch {
        /* ignore malformed frame */
      }
    }
  }
}
