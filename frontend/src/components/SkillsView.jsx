import { useState } from 'react';
import { Icon } from './ui.jsx';
import { timeAgo } from '../util.js';
import SkillEditor from './SkillEditor.jsx';

const GLYPHS = {
  chart: Icon.Layers,
  table: Icon.Panel,
  doc: Icon.Folder,
  layers: Icon.Layers,
  bundle: Icon.Zip,
  search: Icon.Search,
  spark: Icon.Spark,
};

/**
 * Skills — the agent's reusable procedures.
 *
 * A skill is a SKILL.md in `skills/`. The catalogue (name + one-liner) sits in
 * the system prompt; the body is loaded only when it is needed — either because
 * the router matched the request (triggers / attached file types) or because the
 * agent called `use_skill`. `uses` shows composition: that skill pulls in the
 * skills it depends on. Anything here can be authored by the user, or by the
 * agent itself through the `create_skill` tool.
 */
export default function SkillsView({
  skills,
  onToggle,
  onTry,
  onRefresh,
  onCreate,
  onUpdate,
  onDelete,
  onRoute,
}) {
  const [editing, setEditing] = useState(null); // null | {} (new) | skill
  const [saving, setSaving] = useState(false);
  const [probe, setProbe] = useState('');
  const [matches, setMatches] = useState(null);

  const active = skills.filter((s) => s.enabled).length;
  const custom = skills.filter((s) => s.author && s.author !== 'builtin').length;

  async function save(payload) {
    setSaving(true);
    try {
      if (editing?.name) await onUpdate(editing.name, payload);
      else await onCreate(payload);
      setEditing(null);
    } finally {
      setSaving(false);
    }
  }

  async function runProbe(value) {
    setProbe(value);
    if (!value.trim()) return setMatches(null);
    try {
      setMatches(await onRoute(value));
    } catch {
      setMatches([]);
    }
  }

  return (
    <section className="screen" aria-label="Skills">
      <div className="screen-head">
        <div>
          <h2>Skills</h2>
          <p>
            {active} of {skills.length} enabled{custom > 0 ? ` · ${custom} yours` : ''}. The router
            reads your words and your attachments and loads the matching skill <em>before</em> the
            agent answers — no tool call needed. Skills can call other skills, which is how the
            report bundle composes four of them.
          </p>
        </div>
        <div className="screen-actions">
          <button type="button" className="btn btn-ghost" onClick={onRefresh}>
            Refresh
          </button>
          <button type="button" className="btn btn-primary" onClick={() => setEditing({})}>
            <Icon.Plus size={15} />
            New skill
          </button>
        </div>
      </div>

      {/* router tester — makes the auto-loading inspectable instead of magic */}
      <div className="router-box">
        <label className="router-probe">
          <Icon.Search size={15} />
          <input
            value={probe}
            onChange={(e) => runProbe(e.target.value)}
            placeholder='Test the router: "read this PDF", "clean the csv", "chart the scores"…'
            aria-label="Test which skill the router would load"
          />
        </label>
        <div className="router-result" aria-live="polite">
          {matches === null ? (
            <span className="router-idle">
              Type a request to see which skill auto-loads. Attachments count too — a{' '}
              <code>.pdf</code> pulls in the PDF skill, a <code>.csv</code> pulls in the data
              wrangler.
            </span>
          ) : matches.length === 0 ? (
            <span className="router-idle">No skill matches — the agent answers directly.</span>
          ) : (
            matches.map((m) => (
              <span className="router-match" key={m.name}>
                <b>{m.name}</b>
                <em>{m.reasons.join(' · ')}</em>
              </span>
            ))
          )}
        </div>
      </div>

      <div className="skill-grid">
        {skills.map((skill, i) => {
          const Glyph = GLYPHS[skill.icon] || Icon.Spark;
          const isMine = skill.author && skill.author !== 'builtin';
          return (
            <article
              key={skill.name}
              className={`skill ${skill.enabled ? 'is-on' : ''} ${skill.error ? 'is-broken' : ''} ${
                isMine ? 'is-mine' : ''
              }`}
              style={{ '--i': i }}
            >
              <div className="skill-top">
                <span className="skill-glyph" aria-hidden="true">
                  <Glyph size={19} />
                </span>
                <div className="skill-titles">
                  <h3>
                    {skill.title}
                    {isMine && (
                      <span className="skill-badge">
                        {skill.author === 'agent' ? 'by the agent' : 'yours'}
                      </span>
                    )}
                  </h3>
                  <code className="skill-slug">use_skill("{skill.name}")</code>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={skill.enabled}
                  aria-label={`${skill.enabled ? 'Disable' : 'Enable'} ${skill.title}`}
                  className={`switch ${skill.enabled ? 'is-on' : ''}`}
                  onClick={() => onToggle(skill)}
                >
                  <span />
                </button>
              </div>

              <p className="skill-desc">{skill.description}</p>

              {skill.when_to_use && (
                <p className="skill-when">
                  <b>Use when</b> {skill.when_to_use}
                </p>
              )}

              {(skill.triggers?.length > 0 || skill.files?.length > 0) && (
                <div className="skill-uses skill-auto">
                  <span>Auto-loads on</span>
                  {(skill.triggers || []).slice(0, 4).map((t) => (
                    <code key={t}>{t}</code>
                  ))}
                  {(skill.files || []).map((f) => (
                    <code key={f} className="file-tag">
                      .{f}
                    </code>
                  ))}
                </div>
              )}

              {skill.uses?.length > 0 && (
                <div className="skill-uses">
                  <span>Calls</span>
                  {skill.uses.map((u) => (
                    <code key={u}>{u}</code>
                  ))}
                </div>
              )}

              {skill.error && <p className="skill-error">{skill.error}</p>}

              <div className="skill-foot">
                <span className="skill-runs">
                  {skill.runs > 0 ? `${skill.runs} run${skill.runs === 1 ? '' : 's'}` : 'never run'}
                  {skill.last_used ? ` · ${timeAgo(skill.last_used)}` : ''}
                </span>
                {isMine && (
                  <>
                    <button
                      type="button"
                      className="mini-btn"
                      onClick={() => setEditing(skill)}
                      aria-label={`Edit ${skill.title}`}
                    >
                      <Icon.Pencil size={14} />
                    </button>
                    <button
                      type="button"
                      className="mini-btn danger"
                      onClick={() => onDelete(skill)}
                      aria-label={`Delete ${skill.title}`}
                    >
                      <Icon.Trash size={14} />
                    </button>
                  </>
                )}
                <button type="button" className="mini-btn" onClick={() => onTry(skill)}>
                  <Icon.Spark size={14} />
                  Try it
                </button>
              </div>
            </article>
          );
        })}
      </div>

      <p className="connector-note">
        <Icon.Cpu size={15} />
        <span>
          Skills live in <code>skills/&lt;name&gt;/SKILL.md</code> — markdown, no code. Create one
          here, drop a folder in, or just ask in chat (“save that as a skill”) and the agent writes
          it with <code>create_skill</code>. Routing needs no model call: phrases and file types in
          the frontmatter decide it.
        </span>
      </p>

      <SkillEditor
        open={editing !== null}
        skill={editing?.name ? editing : null}
        existingNames={skills.map((s) => s.name)}
        saving={saving}
        onClose={() => setEditing(null)}
        onSave={save}
      />
    </section>
  );
}
