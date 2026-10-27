/**
 * Agent phases → orb states.
 *
 * Each entry maps a *real* thing the backend is doing (it is derived from the
 * SSE stream, not from a timer) to one of the nine ThinkingOrb animations, so
 * the indicator always tells the truth about what the agent is up to.
 */
export const PHASES = {
  idle: { id: 'idle', orb: 'breathing', label: 'Idle' },
  searching: { id: 'searching', orb: 'searching', label: 'Reasoning' },
  executing: { id: 'executing', orb: 'working', label: 'Running command' },
  connecting: { id: 'connecting', orb: 'connecting', label: 'Calling tool' },
  solving: { id: 'solving', orb: 'solving', label: 'Reading results' },
  composing: { id: 'composing', orb: 'composing', label: 'Composing response' },
};

/** Map a raw SSE event to the phase it implies. */
export function phaseForEvent(type, payload) {
  switch (type) {
    case 'status':
      return { phase: PHASES.searching, detail: null };
    case 'command_start':
      return { phase: PHASES.executing, detail: payload?.command || null };
    case 'command_done':
      return { phase: PHASES.solving, detail: null };
    case 'connector_start':
      return { phase: PHASES.connecting, detail: payload?.tool || null };
    case 'connector_done':
      return { phase: PHASES.solving, detail: null };
    case 'done':
      return { phase: PHASES.composing, detail: null };
    default:
      return null;
  }
}
