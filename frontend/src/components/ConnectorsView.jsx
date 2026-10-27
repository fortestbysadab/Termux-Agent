import { BrandMark, brandIcon } from '../brandIcons.jsx';
import { Icon, Button, Badge } from './ui.jsx';

/**
 * Connector catalogue.
 *
 * Each integration shows its real brand mark (simple-icons, bundled locally).
 * The "live" dot next to the mark tells you what the agent is doing with it —
 * a pulsing ring while a tool from that connector is being called.
 */
export default function ConnectorsView({
  connectors,
  onToggle,
  onConfigure,
  onAddMcp,
  onDelete,
  liveConnector,
}) {
  const active = connectors.filter((c) => c.enabled).length;
  const mcpNative = connectors.filter((c) => c.kind !== 'builtin').length;

  return (
    <section className="screen" aria-label="Connectors">
      <div className="screen-head">
        <div>
          <h2>Connectors</h2>
          <p>
            {active} of {connectors.length} connected{mcpNative > 0 ? ` · ${mcpNative} custom MCP` : ''}.
            Enabled tools are injected into the agent&apos;s tool list for every turn.
          </p>
        </div>
        <Button variant="primary" onClick={onAddMcp}>
          <Icon.Plus size={16} />
          Add MCP server
        </Button>
      </div>

      <div className="connector-grid">
        {connectors.map((c, i) => {
          const known = Boolean(brandIcon(c.id));
          const live = liveConnector === c.id;

          return (
            <article
              key={c.id}
              className={`connector ${c.enabled ? 'is-on' : ''} ${live ? 'is-live' : ''}`}
              style={{ '--i': i }}
            >
              <div className="connector-top">
                <span className={`brand-tile ${known ? '' : 'is-generic'}`} aria-hidden="true">
                  <BrandMark id={c.id} size={24} muted={!known} />
                  <i className={`brand-state ${c.enabled ? 'on' : ''} ${live ? 'live' : ''}`} />
                </span>

                <div className="connector-titles">
                  <h3>{c.name}</h3>
                  <span className="connector-badges">
                    {c.enabled ? <Badge tone="ok">Connected</Badge> : <Badge tone="muted">Available</Badge>}
                    <Badge tone="muted">{c.kind === 'builtin' ? 'REST' : 'MCP'}</Badge>
                    {c.is_configured && c.fields?.length > 0 && <Badge tone="muted">Key set</Badge>}
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

      <p className="connector-note">
        <Icon.Cpu size={15} />
        <span>
          Built-ins are thin REST wrappers kept for convenience. The industry-standard way to
          connect new tools is <b>MCP</b> — add any Model Context Protocol server and its tools
          appear to the agent automatically.
        </span>
      </p>
    </section>
  );
}
