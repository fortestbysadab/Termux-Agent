import { useEffect, useState } from 'react';
import { Modal, Field, Button } from './ui.jsx';

export function ConnectorConfigModal({ connector, onClose, onSubmit, saving }) {
  const [values, setValues] = useState({});

  useEffect(() => {
    setValues({});
  }, [connector?.id]);

  const open = Boolean(connector);
  const fields = connector?.fields || [];

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Connect ${connector?.name ?? ''}`}
      subtitle={connector?.description}
      size="sm"
    >
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit?.(connector, values);
        }}
      >
        {fields.map((f) => (
          <Field key={f.key} label={f.label} htmlFor={`f-${f.key}`}>
            <input
              id={`f-${f.key}`}
              type={f.type || 'text'}
              required={f.required}
              autoComplete="off"
              spellCheck="false"
              value={values[f.key] || ''}
              onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
            />
          </Field>
        ))}
        <p className="form-note">
          Credentials are stored in the local SQLite database on this device and never leave it.
        </p>
        <div className="form-actions">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save & connect'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

const MCP_COMMAND_HINT =
  'npx -y @modelcontextprotocol/server-postgres postgresql://localhost/db';

export function AddMcpModal({ open, onClose, onSubmit, saving }) {
  const [form, setForm] = useState({
    name: '',
    kind: 'mcp_stdio',
    command: '',
    url: '',
    description: '',
  });

  useEffect(() => {
    if (!open) setForm({ name: '', kind: 'mcp_stdio', command: '', url: '', description: '' });
  }, [open]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a custom MCP server"
      subtitle="Any Model Context Protocol server — local stdio or a remote HTTP endpoint."
      size="sm"
    >
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          const config =
            form.kind === 'mcp_stdio' ? { command: form.command.trim() } : { url: form.url.trim() };
          onSubmit?.({
            name: form.name.trim(),
            kind: form.kind,
            description: form.description.trim() || 'Custom MCP connector',
            config,
          });
        }}
      >
        <Field label="Display name" htmlFor="mcp-name">
          <input
            id="mcp-name"
            required
            placeholder="PostgreSQL"
            value={form.name}
            onChange={set('name')}
          />
        </Field>

        <Field label="Transport" htmlFor="mcp-kind">
          <select id="mcp-kind" value={form.kind} onChange={set('kind')}>
            <option value="mcp_stdio">stdio — local command</option>
            <option value="mcp_sse">HTTP — remote endpoint</option>
          </select>
        </Field>

        {form.kind === 'mcp_stdio' ? (
          <Field label="Command" htmlFor="mcp-command" hint="Run with the agent's environment.">
            <input
              id="mcp-command"
              required
              placeholder={MCP_COMMAND_HINT}
              value={form.command}
              onChange={set('command')}
            />
          </Field>
        ) : (
          <Field label="Endpoint URL" htmlFor="mcp-url" hint="JSON-RPC over HTTP.">
            <input
              id="mcp-url"
              type="url"
              required
              placeholder="https://example.com/mcp"
              value={form.url}
              onChange={set('url')}
            />
          </Field>
        )}

        <Field label="Description" htmlFor="mcp-desc">
          <input
            id="mcp-desc"
            placeholder="What does this server expose?"
            value={form.description}
            onChange={set('description')}
          />
        </Field>

        <div className="form-actions">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={saving}>
            {saving ? 'Adding…' : 'Add connector'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
