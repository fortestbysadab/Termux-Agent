import { Icon } from './ui.jsx';
import { timeAgo } from '../util.js';

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
 * A skill is a SKILL.md in `skills/`. The catalogue (name + one-liner) is in the
 * system prompt; the full procedure is loaded only when the agent calls
 * `use_skill`, which is how the prompt stays small. `uses` shows composition:
 * that skill loads the skills it depends on when it runs.
 */
export default function SkillsView({ skills, onToggle, onTry, onRefresh }) {
  const active = skills.filter((s) => s.enabled).length;

  return (
    <section className="screen" aria-label="Skills">
      <div className="screen-head">
        <div>
          <h2>Skills</h2>
          <p>
            {active} of {skills.length} enabled. When a request matches a skill, the agent loads it
            first and follows its steps — a skill can call other skills, which is how the report
            bundle composes four of them.
          </p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={onRefresh}>
          Refresh
        </button>
      </div>

      <div className="skill-grid">
        {skills.map((skill, i) => {
          const Glyph = GLYPHS[skill.icon] || Icon.Spark;
          return (
            <article
              key={skill.name}
              className={`skill ${skill.enabled ? 'is-on' : ''} ${skill.error ? 'is-broken' : ''}`}
              style={{ '--i': i }}
            >
              <div className="skill-top">
                <span className="skill-glyph" aria-hidden="true">
                  <Glyph size={19} />
                </span>
                <div className="skill-titles">
                  <h3>{skill.title}</h3>
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
          Skills live in <code>skills/&lt;name&gt;/SKILL.md</code> — a directory of markdown, no code
          required. Drop a new folder in and refresh; the catalogue is re-scanned on every request.
        </span>
      </p>
    </section>
  );
}
