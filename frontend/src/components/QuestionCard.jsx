import { useEffect, useMemo, useState } from 'react';
import { Icon } from './ui.jsx';

/**
 * "Input required" — the agent paused and is asking, with options.
 *
 * This is the client half of a MCP-style round-trip: the turn already ended
 * server-side, and picking answers re-issues the same request with
 * `input_responses` + `request_state`. So nothing is lost by answering late.
 */
export default function QuestionCard({ request, onSubmit, onDismiss }) {
  const [picked, setPicked] = useState({});
  const [custom, setCustom] = useState({});

  useEffect(() => {
    setPicked({});
    setCustom({});
  }, [request?.request_state]);

  const questions = request?.questions || [];
  const answered = useMemo(
    () =>
      questions.every((q) => picked[q.id] || (custom[q.id] || '').trim().length > 0),
    [questions, picked, custom],
  );

  if (!request) return null;

  function choose(question, option) {
    setPicked((p) => ({ ...p, [question.id]: option.label }));
    setCustom((c) => ({ ...c, [question.id]: '' }));
  }

  function submit() {
    const responses = {};
    for (const question of questions) {
      const typed = (custom[question.id] || '').trim();
      const value = typed || picked[question.id];
      if (value) responses[question.id] = value;
    }
    onSubmit(responses);
  }

  return (
    <div className="ask-card" role="group" aria-label="The agent needs an answer">
      <div className="ask-head">
        <span className="ask-badge">
          <Icon.Route size={12} />
          needs your input
        </span>
        {onDismiss && (
          <button type="button" className="ask-x" onClick={onDismiss} aria-label="Dismiss">
            <Icon.Close size={13} />
          </button>
        )}
      </div>

      {request.intro && <p className="ask-intro">{request.intro}</p>}

      {questions.map((question) => (
        <div className="ask-q" key={question.id}>
          <p className="ask-question">{question.question}</p>
          <div className="ask-options">
            {question.options.map((option) => {
              const on = picked[question.id] === option.label && !custom[question.id];
              return (
                <button
                  type="button"
                  key={option.id}
                  className={`ask-option ${on ? 'is-on' : ''}`}
                  aria-pressed={on}
                  onClick={() => choose(question, option)}
                >
                  <b>{option.label}</b>
                  {option.description && <span>{option.description}</span>}
                </button>
              );
            })}
          </div>
          {question.allow_custom && (
            <input
              className="ask-custom"
              value={custom[question.id] || ''}
              placeholder="…or type your own answer"
              onChange={(e) => {
                setCustom((c) => ({ ...c, [question.id]: e.target.value }));
                setPicked((p) => ({ ...p, [question.id]: '' }));
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && answered) submit();
              }}
            />
          )}
        </div>
      ))}

      <div className="ask-foot">
        <button type="button" className="btn btn-primary" disabled={!answered} onClick={submit}>
          Continue
        </button>
        <span className="ask-hint">Your answers re-send the same request — nothing restarts.</span>
      </div>
    </div>
  );
}
