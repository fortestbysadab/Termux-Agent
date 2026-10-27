/**
 * Agent roster — every worker in the workspace gets a stable visual identity
 * (Bot Avatars `type` + colour) so the user can tell at a glance which part of
 * the system is acting: the planner, the shell, or an MCP bridge.
 */

export const AGENTS = {
  assistant: {
    id: 'assistant',
    name: 'Termux Agent',
    role: 'Planner & orchestrator',
    bot: { type: 'clover', color: '#8b7cf6', shading: 'fabric' },
  },
  terminal: {
    id: 'terminal',
    name: 'Shell',
    role: 'Bash executor',
    bot: { type: 'mech', color: '#3fc8b4', shading: 'plastic' },
  },
  connector: {
    id: 'connector',
    name: 'MCP Bridge',
    role: 'External tools',
    bot: { type: 'hexagon', color: '#f0a35e', shading: 'plastic' },
  },
  skill: {
    id: 'skill',
    name: 'Skill',
    role: 'Loaded procedure',
    bot: { type: 'star', color: '#f2c14e', shading: 'plastic' },
  },
};

/** Which worker is acting, given the live tool that is running. */
export function agentForTool(tool) {
  if (!tool) return AGENTS.assistant;
  if (tool === 'terminal') return AGENTS.terminal;
  if (String(tool).startsWith('use_skill') || tool === 'list_skills') return AGENTS.skill;
  return AGENTS.connector;
}

/**
 * Per-connector identities: shape + tint per integration, so the connectors
 * grid reads as a roster of distinct teammates rather than twelve identical
 * plug icons.
 */
export const CONNECTOR_BOTS = {
  github: { type: 'ghost', color: '#8b93a8' },
  drive: { type: 'cloud', color: '#43b581' },
  docs: { type: 'pill', color: '#5b9bfa' },
  notion: { type: 'square', color: '#b9bec9' },
  gmail: { type: 'triangle', color: '#f2685c' },
  linear: { type: 'hexagon', color: '#8b8ff0' },
  calendar: { type: 'circle', color: '#5b9bfa' },
  slides: { type: 'blob', color: '#f2b23c' },
  sheets: { type: 'drop', color: '#3fb984' },
  dropbox: { type: 'pebble', color: '#4f8ff7' },
  vercel: { type: 'star', color: '#c9cdd8' },
  supabase: { type: 'droid', color: '#4bd6a0' },
};

const FALLBACK_BOTS = ['flower', 'alien', 'cat', 'puddle', 'ice'];

export function botForConnector(id) {
  if (CONNECTOR_BOTS[id]) return CONNECTOR_BOTS[id];
  // Custom MCP servers: derive a stable shape from the id so it never changes.
  let h = 0;
  for (let i = 0; i < id.length; i += 1) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return { type: FALLBACK_BOTS[h % FALLBACK_BOTS.length], color: '#a78bfa' };
}
