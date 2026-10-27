import { useEffect, useRef, useState } from 'react';
import { BotAvatar } from 'bot-avatars';
import { ThinkingOrb } from 'thinking-orbs';

/**
 * Bot Avatars — every agent in the workspace has a stable body + colour, so
 * "who is acting" is readable without reading the text. The `state` prop is
 * wired to the real agent lifecycle:
 *   working  → the agent owns the current turn and is doing something
 *   default  → idle, waiting on the user
 *   sleeping → inactive (disabled connector, parked session)
 */
/**
 * Only animate what the user can actually see: an avatar scrolled out of view
 * is frozen, which keeps a screen full of connector bots cheap on a phone.
 */
function useInView(ref) {
  const [inView, setInView] = useState(true);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === 'undefined') return undefined;
    const io = new IntersectionObserver(
      ([entry]) => setInView(entry.isIntersecting),
      { rootMargin: '120px' },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [ref]);
  return inView;
}

export function AgentAvatar({
  agent,
  state = 'default',
  size = 34,
  theme = 'dark',
  reduced = false,
  interactive = false,
}) {
  const { bot } = agent;
  const hostRef = useRef(null);
  const inView = useInView(hostRef);
  return (
    <span
      ref={hostRef}
      className="agent-avatar"
      style={{ width: size, height: size }}
      title={`${agent.name} · ${agent.role}`}
    >
      {/* keyed so a different agent crossfades in instead of morphing in place */}
      <span key={agent.id} className="agent-avatar-swap">
        <BotAvatar
          type={bot.type}
          color={bot.color}
          shading={bot.shading}
          state={state}
          size={size}
          theme={theme}
          // Only prefers-reduced-motion freezes the avatar — an idle agent still
          // looks alive (blinks, glances around, hops now and then).
          paused={reduced || !inView}
          interactive={interactive}
          saturation={1.4}
          brightness={1.04}
          speed={state === 'working' ? 1.15 : 0.9}
          seed={0.37}
        />
      </span>
    </span>
  );
}

/**
 * Thinking Orbs — replaces every spinner in the product. Orb states are bound
 * to real agent phases (see activity.js), and switching phases crossfades the
 * two canvases so the transition never snaps.
 */
function useCrossfade(value, duration = 340) {
  const [pair, setPair] = useState({ current: value, previous: null });

  useEffect(() => {
    let timer;
    setPair((prev) => {
      if (prev.current === value) return prev;
      return { current: value, previous: prev.current };
    });
    timer = setTimeout(() => {
      setPair((prev) => (prev.current === value ? { current: value, previous: null } : prev));
    }, duration);
    return () => clearTimeout(timer);
  }, [value, duration]);

  return pair;
}

export function OrbSwap({ state, theme = 'dark', size = 20, reduced = false, speed = 1 }) {
  const { current, previous } = useCrossfade(state);
  return (
    <span className="orb-swap" style={{ width: size, height: size }} aria-hidden="true">
      {previous && (
        <span className="orb-layer is-out">
          <ThinkingOrb
            state={previous}
            size={size}
            theme={theme}
            paused={reduced}
            speed={speed}
          />
        </span>
      )}
      <span className="orb-layer is-in" key={current}>
        <ThinkingOrb state={current} size={size} theme={theme} paused={reduced} speed={speed} />
      </span>
    </span>
  );
}

/**
 * The activity line: orb + verb + the thing the agent is touching right now.
 * Announced politely to screen readers so the stream is not silent for AT.
 */
export function ActivityLine({ phase, detail, theme, reduced, size = 20, elapsed }) {
  return (
    <div className="activity" role="status" aria-live="polite">
      <OrbSwap state={phase.orb} theme={theme} size={size} reduced={reduced} />
      <div className="activity-body">
        <span className="activity-label">{phase.label}</span>
        {detail && <code className="activity-detail">{detail}</code>}
      </div>
      {elapsed != null && <span className="activity-timer" aria-hidden="true">{elapsed}s</span>}
    </div>
  );
}
