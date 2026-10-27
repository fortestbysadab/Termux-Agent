# Console frontend (React + Libraries.dev)

The web console is a React 18 app, bundled **once** into `web/static/app.js` +
`web/static/app.css` and served by the Python server exactly like before.

```bash
cd frontend
npm install        # first time only
npm run build      # → ../web/static/{app.js,app.css,index.html}
npm run watch      # rebuild on change while editing
```

**Node is a build-time tool only.** The shipped app still boots with
`python3 main.py` on a fresh Termux install — no npm, no server-side JS, no CDN,
no runtime network calls. That is why `web/static/app.js` is committed.

---

## Libraries.dev components

| Library | Package | Where it is used |
| --- | --- | --- |
| **Border Beam** | `border-beam@1.4.1` | **Only** the chat composer (`components/Composer.jsx`) |
| **Thinking Orbs** | `thinking-orbs@0.3.2` | Activity line, tool cards, sidebar/topbar status, hero, all "thinking" states |
| **Bot Avatars** | `bot-avatars@0.2.2` | Assistant identity, per-tool worker identities, connector roster |

### Border Beam is composer-only — by design

It wraps nothing but the input. The beam is a property of *the act of talking to
the agent*, so reusing it on cards would dilute it and add visual noise.

| State | duration | strength | brightness | glow |
| --- | --- | --- | --- | --- |
| Idle | 5.2 s | 0.62 dark / 0.92 light | 1.16 / 1.30 | 0.95 |
| Working (`busy`) | 2.6 s | 1.0 | 1.34 / 1.26 | 1.10 |

It is `active={false}` under `prefers-reduced-motion`, and light theme gets a
higher brightness/strength because a glow needs more push to read on white.

### Thinking Orbs ← real agent activity

The orb state is derived from the SSE stream, not from a timer (`src/activity.js`):

| Backend event | Phase label | Orb state |
| --- | --- | --- |
| `status` (planner turn) | Reasoning | `searching` |
| `command_start` | Running command | `working` |
| `command_done` | Reading results | `solving` |
| `connector_start` | Calling tool | `connecting` |
| `connector_done` | Reading results | `solving` |
| — (turn finished) | — | crossfades out |
| idle session / empty state | — | `breathing` / `weaving` |

State changes **crossfade** two canvases (`OrbSwap`, 340 ms) instead of snapping.
Orbs are `aria-hidden`; the text next to them lives in an `aria-live="polite"`
region so screen readers hear the phase changes.

### Bot Avatars ← real agent lifecycle

Three identities, each a distinct body + colour, so "who is acting" is legible
at a glance:

| Agent | Avatar | State wiring |
| --- | --- | --- |
| Planner (`assistant`) | clover, violet, plush | `working` while the turn streams, `default` when idle |
| Shell (`terminal`) | mech, teal, plastic | becomes the turn avatar the moment a bash command starts |
| MCP (`connector`) | hexagon, amber, plastic | becomes the turn avatar during connector calls |

The connectors screen renders one avatar per integration (`src/agents.js` maps
each connector id to a stable shape + tint): **enabled → `default`**, **disabled
→ `sleeping`**, **being called right now → `working`**.

Performance: avatars are frozen when scrolled out of view (`IntersectionObserver`)
and under reduced motion, and connectors use the cheaper `plastic` shading.

---

## Source map

```text
frontend/
├── build.mjs              # esbuild → ../web/static
├── index.html             # copied verbatim; theme pre-paint script
└── src/
    ├── main.jsx           # root + error boundary
    ├── App.jsx            # state, SSE stream, layout, shortcuts
    ├── api.js             # REST + SSE client
    ├── activity.js        # SSE event → orb phase mapping
    ├── agents.js          # agent roster + connector identities
    ├── util.js            # formatting, theme hooks, markdown → React nodes
    ├── styles.css         # design tokens, light/dark, layout, motion
    └── components/
        ├── AgentAvatar.jsx  # BotAvatar + ThinkingOrb wrappers (OrbSwap, ActivityLine)
        ├── Composer.jsx     # BorderBeam + autosizing textarea
        ├── MessageTurn.jsx  # one conversation turn
        ├── cards.jsx        # tool runs, artifacts, error cards
        ├── Sidebar.jsx  Topbar.jsx  WorkspacePanel.jsx
        ├── ConnectorsView.jsx  FilesView.jsx
        ├── Modals.jsx       # connector credentials, custom MCP
        └── PreviewModal.jsx # xlsx/csv table, pdf card, image, text
```

## Notes for future work

- **Markdown** is rendered to React nodes (`renderMarkdown` in `util.js`) — there
  is no `innerHTML` anywhere, so model output cannot inject markup.
- **Streaming**: `POST /api/chat` returns `text/event-stream`, so the client
  reads `resp.body` and parses frames manually (`api.js`); `EventSource` cannot
  do POST.
- **Tool runs**: kept in a ref *and* in React state while streaming, because the
  server's `done` payload does not always repeat them — the transcript should
  still show what ran.
- **Theme**: `<html data-theme>` is always a concrete `light` | `dark`
  (`system` is resolved before paint) so both the CSS token blocks and the
  Libraries.dev `theme="auto"` detection resolve correctly.
