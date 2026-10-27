# Console redesign — implementation notes

Redesign of the Termux Agent console into a React 18 workspace built on
[Libraries.dev](https://libraries.dev) components, with the Python backend left
functionally untouched.

- Live app: `python3 main.py` → `http://localhost:8080`
- Source: [`frontend/`](frontend/README.md) · Build: `cd frontend && npm run build`
- Screenshots: [`../design-review/`](../design-review) (dark, light, mobile, live states)

---

## 1. What was there before

`web/static/app.js` was 1,357 lines of hand-written vanilla JS building DOM by
string concatenation, with hand-rolled canvas re-implementations of the three
Libraries.dev components (`class BotAvatar`, `createThinkingOrb`,
`.border-beam` CSS) — no React, no packages, and Border Beam applied to *three*
places (the status card, the live command card, and the composer).

## 2. What it is now

A React app (`frontend/src`, 14 modules) bundled by esbuild into
`web/static/app.js` + `app.css`. **The real npm packages are used**:
`border-beam@1.4.1`, `thinking-orbs@0.3.2`, `bot-avatars@0.2.2`, React 18.

Runtime dependencies stay at zero: `web/static/` is committed, so Termux users
still only need `pkg install python git`. Node is a build-time tool (`frontend/node_modules`
is git-ignored).

### Backend change (2 edits, both additive)

| File | Change |
| --- | --- |
| `web/server.py` | static handler replaced with `_try_serve_static()` — serves anything under `web/static` with a MIME type, `/` → `index.html`, traversal-safe, `no-cache`. Fixes a latent bug: `/app.css` and `/app.js.map` used to 404. |
| `tests.py` | +2 tests: the console assets exist and are non-empty; the bundle really contains Border Beam / orb / avatar code; index.html references no external URLs. |

All API routes, SSE behaviour, DB schema, sandbox and connectors are unchanged.

---

## 3. The three libraries, wired to the real system

### Border Beam — composer only

```jsx
<BorderBeam colorVariant="ocean" theme={theme} borderRadius={20}
            duration={busy ? 2.6 : 5.2} strength={beam.strength} …>
  <div className="composer"> … textarea + send … </div>
</BorderBeam>
```

It wraps **only** the chat input, in `components/Composer.jsx`. Verified in the
browser: on the chat screen exactly one `[data-beam]` element exists and it is
inside `.composer-beam`; on the connectors and files screens there are zero.

The beam is *stateful but subtle*: slow and low-strength at rest, faster and
brighter while `busy` (a turn is streaming), `active={false}` under
`prefers-reduced-motion`, and slightly stronger on light backgrounds where a
glow needs more push to read. Focus, caret, IME, autosize and Enter-to-send all
behave normally inside it.

### Thinking Orbs — driven by the SSE stream

`src/activity.js` maps backend events to orb states; nothing is on a timer.

| SSE event | Label | Orb |
| --- | --- | --- |
| `status` | Reasoning | `searching` |
| `command_start` | Running command (+ the command text) | `working` |
| `command_done` | Reading results | `solving` |
| `connector_start` | Calling tool (+ tool name) | `connecting` |
| `connector_done` | Reading results | `solving` |
| idle session | — | `breathing` (composer idle) / `weaving` (empty state) |

`OrbSwap` crossfades the outgoing and incoming canvas over 340 ms, so phases
morph instead of snapping. Orbs are `aria-hidden`; the phase text sits in an
`aria-live="polite"` line, and the topbar mirrors the same state for when the
thread is scrolled away.

### Bot Avatars — one identity per worker, state-bound

| Agent | Body | `state` wiring |
| --- | --- | --- |
| Planner "Termux Agent" | clover / violet / plush | `working` while streaming, `default` idle |
| "Shell" (bash) | mech / teal / plastic | becomes the turn avatar when a command starts |
| "MCP Bridge" | hexagon / amber / plastic | becomes the turn avatar during connector calls |
| Sidebar brand | clover | `working` ⇄ `default` with the live turn, status text follows |
| Connector roster (12+) | one shape + tint each | `sleeping` disabled · `default` connected · `working` when currently called |

Cheap by design: `IntersectionObserver` freezes avatars scrolled out of view,
`prefers-reduced-motion` freezes them entirely, connectors use the lighter
`plastic` shading rather than plush `fabric`.

---

## 4. Design system

- **Tokens** (`src/styles.css`): one set of semantic variables for light and dark
  — surfaces, lines, ink ramp, accents, shadows. `<html data-theme>` is always a
  concrete `light|dark` (system preference resolved before first paint), which
  also lets the Libraries.dev `theme="auto"` detection work.
- **Type**: one UI stack, one mono stack, tabular numerals for every counter,
  `letter-spacing` tightened on headings only.
- **Layout**: sidebar (278) · thread (max 800) · workspace (336). The workspace
  is docked on ≥1281 px, a right drawer below that, and the sidebar becomes an
  off-canvas drawer with scrim below 1024 px. `100dvh` throughout for Android.
- **Motion**: `--ease-out` for entrances, 220 ms for state, 380 ms for layout;
  staggered card entrances (18–22 ms). Everything collapses under
  `prefers-reduced-motion`.
- **Accessibility**: visible focus rings, labelled icon buttons, `aria-current`
  nav, `aria-pressed` toggles, dialog roles + Escape + focus restore in modals,
  live regions for agent phases and tool results, `prefers-contrast: more`
  borders, `.sr-only` helpers.

### Usability fixes that came out of testing

- Chat **markdown now renders tables** (models emit them constantly; the old
  renderer printed pipes).
- **Markdown → React nodes**, no `innerHTML` anywhere.
- Completed tool runs stay visible during a live turn (previously they vanished
  once the activity line changed phase).
- Long commands/outputs wrap instead of widening the page; the composer autosizes
  to 200 px then scrolls.
- An **error boundary** replaces the previous failure mode (blank white page).

---

## 5. Verification

| Check | Result |
| --- | --- |
| `python3 tests.py` | 14/14 pass (was 12; +2 console-asset tests) |
| Console errors, all screens, both themes | 0 page errors, 0 console errors |
| Border Beam placement | exactly 1 element, composer-only, all screens |
| Composer behaviour | multiline autosize, focus retained, `Enter` sends, `Shift+Enter` newline |
| Live turn (scripted SSE, `tools/mock_sse.py`) | phases advance search → exec → solve → connect → solve → done; failed command renders as an error card; artifacts land at the end |
| Themes | `system` resolves to dark/light from `prefers-color-scheme` before paint |
| Viewports | 1440×900, 1280×860, 834×1112 (tablet drawer), 390×844 (mobile) |
| Reduced motion | beam inactive, canvases frozen, no animations |
| Preview modal | xlsx → sticky-header table (real OOXML parsed by the backend), svg → image, pdf → card + viewer link, text → pre |

Test harness for the live states (dev only, not shipped): `python3 tools/mock_sse.py 8099`
serves the built console on 8099 and replays a scripted agent turn while proxying
everything else to the real server on 8080.

---

## 6. Known limits

- The bundle is 426 kB uncompressed (React 18 + three canvas libraries); it is
  fine over LAN and for a local app, but it is not a 20 kB page.
- The `done` SSE payload does not always repeat executed commands, so the UI
  keeps its own accumulation; commands are visible but double-recorded if the
  server later starts sending `tool_runs` (they are de-duplicated by preferring
  the server's list when it is non-empty).
- Connector roster avatars are cosmetic identities; they do not reflect per-tool
  live state beyond "this connector is the one being called".
