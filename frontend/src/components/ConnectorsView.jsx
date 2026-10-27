import { AgentAvatar } from './AgentAvatar.jsx';
import { botForConnector } from '../agents.js';
import { Icon, Button, Badge } from './ui.jsx';

/**
 * Connector roster. Each integration is drawn as its own bot with a distinct
 * body and tint — enabled connectors idle and blink, disabled ones are asleep,
 * and the connector currently being called by the agent is working.
 */
export default function ConnectorsView({
  connectors,
  onToggle,
  onConfigure,
  onAddMcp,
  onDelete,
  theme,
  reduced,
  liveConnector,
}) {
  const active = connectors.filter((c) => c.enabled).length;

  return (
    <section className="screen" aria-label="Connectors">
      <div className="screen-head">
        <div>
          <h2>Connectors</h2>
          <p>
            {active} of {connectors.length} connected. Enabled tools are injected into the agent&apos;s
            tool list for every turn.
          </p>
        </div>
        <Button variant="primary" onClick={onAddMcp}>
          <Icon.Plus size={16} />
          Custom MCP server
        </Button>
      </div>

      <div className="connector-grid">
        {connectors.map((c, i) => {
          const bot = botForConnector(c.id);
          const agent = {
            id: c.id,
            name: c.name,
            role: c.kind === 'builtin' ? 'Built-in connector' : 'Custom MCP',
            // Plastic is far cheaper per frame than plush fabric — with a
            // dozen avatars on screen that matters on a phone.
            bot: { ...bot, shading: c.enabled ? 'plastic' : 'flat' },
          };
          const state = liveConnector === c.id ? 'working' : c.enabled ? 'default' : 'sleeping';

          return (
            <article
              key={c.id}
              className={`connector ${c.enabled ? 'is-on' : ''}`}
              style={{ '--i': i }}
            >
              <div className="connector-top">
                <AgentAvatar
                  agent={agent}
                  state={state}
                  size={42}
                  theme={theme}
                  reduced={reduced}
                  interactive
                />
                <div className="connector-titles">
                  <h3>{c.name}</h3>
                  <span className="connector-badges">
                    {c.enabled ? (
                      <Badge tone="ok">Connected</Badge>
                    ) : (
                      <Badge tone="muted">Available</Badge>
                    )}
                    {c.kind !== 'builtin' && <Badge tone="muted">MCP</Badge>}
                    {c.is_configured && c.fields?.length > 0 && (
                      <Badge tone="muted">Key set</Badge>
                    )}
                  </span>
                </div>
              </div>

              <p className="connector-desc">{c.description}</p>

              <div className="connector-actions">
                {c.fields && c.fields.length > 0 && (
                  <Button
                    variant="ghost"
                    onClick={() => onConfigure(c)}
                    title={c.is_configured ? 'Update credentials' : 'Add credentials'}
                  >
                    {c.is_configured ? 'Credentials' : 'Configure'}
                  </Button>
                )}
                {c.kind !== 'builtin' && (
                  <Button variant="ghost" onClick={() => onDelete(c.id)} title="Remove connector">
                    <Icon.Trash size={15} />
                  </Button>
                )}
                <Button
                  variant={c.enabled ? 'ghost' : 'primary'}
                  className="connector-toggle"
                  aria-pressed={c.enabled}
                  onClick={() => onToggle(c)}
                >
                  {c.enabled ? <Icon.Check size={14} /> : null}
                  {c.enabled ? 'Connected' : 'Connect'}
                </Button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
