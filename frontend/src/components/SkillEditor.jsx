import { useEffect, useMemo, useState } from 'react';
import { Icon } from './ui.jsx';

const BLANK = {
  name: '',
  title: '',
  description: '',
  when_to_use: '',
  triggers: '',
  files: '',
  uses: '',
  icon: 'spark',
  body: `## Steps

1. Read the input from \`uploads/\` (or the workspace).
2. Do the work with shell commands.
3. Write the result to a file the user can open.
`,
};

const CSV = (value) =>
  String(value || '')
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);

const slugify = (value) =>
  String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);

/**
 * Create / edit a skill. Everything the router needs is editable here:
 * triggers are the phrases that auto-load the skill, files are the extensions
 * that do the same.
 */
export default function SkillEditor({ open, skill, existingNames, saving, onClose, onSave }) {
  const [form, setForm] = useState(BLANK);

  useEffect(() => {
    if (!open) return;
    setForm(
      skill
        ? {
            ...BLANK,
            ...skill,
            triggers: (skill.triggers || []).join(', '),
            files: (skill.files || []).join(', '),
            uses: (skill.uses || []).join(', '),
          }
        : BLANK,
    );
  }, [open, skill]);

  const editing = Boolean(skill);
  const slug = editing ? form.name : slugify(form.name || form.title);
  const clash = !editing && existingNames.includes(slug);
  const valid =
    slug.length > 1 && form.description.trim() && form.body.trim() && !clash && !saving;

  const preview = useMemo(
    () =>
      [
        '- name:',
        `  title: ${form.title || slug || '—'}`,
        `  description: ${form.description || '—'}`,
        `  when_to_use: ${form.when_to_use || '—'}`,
        `  triggers: ${form.triggers || '—'}`,
        `  files: ${form.files || '—'}`,
        `  uses: ${form.uses || '—'}`,
      ].join('\n'),
    [form, slug],
  );

  if (!open) return null;

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <div className="modal-scrim" role="dialog" aria-modal="true" aria-label={editing ? 'Edit skill' : 'New skill'}>
      <div className="modal modal-lg skill-editor">
        <header className="modal-head">
          <div>
            <h2>{editing ? `Edit ${skill.title}` : 'New skill'}</h2>
            <p className="modal-sub">
              A skill is markdown the agent loads when your words (or your files) match it.
            </p>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            <Icon.Close size={16} />
          </button>
        </header>

        <div className="modal-body">
          <div className="field-row">
            <label className="field">
              <span>Title</span>
              <input
                value={form.title}
                onChange={set('title')}
                placeholder="Weekly status report"
                autoFocus
              />
            </label>
            <label className="field">
              <span className="field-label">Name <em>slug</em></span>
              <input
                value={slug}
                onChange={editing ? undefined : set('name')}
                readOnly={editing}
                placeholder="weekly-status-report"
              />
              {clash && <small className="field-err">A skill with that name already exists.</small>}
            </label>
          </div>

          <label className="field">
            <span className="field-label">What it produces</span>
            <input
              value={form.description}
              onChange={set('description')}
              placeholder="Roll the week into one markdown brief with decisions and owners."
            />
          </label>

          <label className="field">
            <span className="field-label">When the agent should use it</span>
            <input
              value={form.when_to_use}
              onChange={set('when_to_use')}
              placeholder="The user asks for a weekly status update or a summary of the week."
            />
          </label>

          <div className="field-row">
            <label className="field">
              <span className="field-label">Router triggers <em>comma separated</em></span>
              <input
                value={form.triggers}
                onChange={set('triggers')}
                placeholder="weekly status, standup, week summary"
              />
            </label>
            <label className="field">
              <span className="field-label">File types <em>auto-load on</em></span>
              <input
                value={form.files}
                onChange={set('files')}
                placeholder="csv, pdf"
              />
            </label>
          </div>

          <label className="field">
            <span className="field-label">Uses other skills <em>comma separated, optional</em></span>
            <input
              value={form.uses}
              onChange={set('uses')}
              placeholder={existingNames.slice(0, 3).join(', ')}
            />
          </label>

          <label className="field">
            <span className="field-label">Instructions</span>
            <textarea
              value={form.body}
              onChange={set('body')}
              rows={9}
              spellCheck="false"
              className="code-area"
            />
          </label>

          <details className="field-note">
            <summary>How the router will see it</summary>
            <pre>{preview}</pre>
          </details>
        </div>

        <footer className="skill-editor-foot">
          <span className="modal-hint">
            {slug ? (
              <>
                Saves to <code>skills/{slug}/SKILL.md</code>
              </>
            ) : (
              'Give it a name to continue'
            )}
          </span>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!valid}
            onClick={() =>
              onSave({
                name: slug,
                title: form.title || undefined,
                description: form.description,
                when_to_use: form.when_to_use,
                triggers: CSV(form.triggers),
                files: CSV(form.files).map((f) => f.replace(/^\./, '')),
                uses: CSV(form.uses),
                icon: form.icon || 'spark',
                body: form.body,
              })
            }
          >
            {saving ? 'Saving…' : editing ? 'Save changes' : 'Create skill'}
          </button>
        </footer>
      </div>
    </div>
  );
}
