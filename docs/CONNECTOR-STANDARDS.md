# Is this connector method the industry standard?

**Short answer:** the *agent loop* is exactly the industry standard. The *connector catalog* is half standard, half home-made. You are not doing anything wrong — but one layer is behind where the industry converged, and it happens to be the layer you were unsure about.

---

## 1. What "talking to data with a connector" actually decomposes into

Three independent layers get confused when people say "connector":

| Layer | Question it answers | In this repo | Standard? |
|---|---|---|---|
| **A. Tool-calling loop** | How does the model ask for an action and get a result back? | `agent/loop.py` — JSON tool schemas → model returns a call → we execute → we feed back the result | ✅ **Yes. Exactly the OpenAI / Gemini function-calling shape.** |
| **B. Tool transport / discovery** | How does an *arbitrary* external service declare its tools and get called? | `connectors/builtin.py` (hand-written REST calls) + `connectors/mcp_client.py` (real MCP client) | ⚠️ **Half. The custom path is bespoke; the MCP path is the standard.** |
| **C. Knowledge retrieval** | How does the model "know" a large unstructured corpus (docs, mail, tickets)? | Not implemented — the agent reads files in the workspace instead | ❌ Not standard for big corpora (that's RAG), but fine at this scale. |

So "talk with any data in this method" is **right at layer A and mostly right at layer B**, and you should not rebuild layer A. Nobody has a better loop right now.

---

## 2. Layer A — the loop: you are dead-on

`run_turn` builds a `tools: [...]` array of JSON-Schema functions, sends the conversation to an OpenAI-compatible `/chat/completions` endpoint, and loops on `tool_calls` until the model stops asking. That is the same contract used by OpenAI's function calling, Google's function calling, and every serious agent framework. Nothing to change.

---

## 3. Layer B — the connector layer: this is the part that isn't standard

Today you have two connector kinds:

- `builtin` — a **hand-written Python function per service** (`github_list_repos`, `drive_search`, …) that builds an HTTP request by hand. Correct, but it means **N services = N code changes**. This is how everyone did integrations in 2023–24 (LangChain tools, Zapier-style REST wrappers).
- `mcp_stdio` / `mcp_sse` — a **real Model Context Protocol client** that spawns a server over stdio or talks JSON-RPC over HTTP, calls `tools/list`, converts MCP tool schemas to OpenAI tool schemas with a per-connector prefix, and routes calls back. That is the standard.

The gap is not that the connector idea is wrong — it's that **the built-ins are a private catalog instead of a subset of a public one**. Practically that means: adding a service (say "Jira") requires you to write Python; in the standard model you point the app at a Jira MCP server and it just appears in the tool list.

### What the industry actually settled on

MCP is no longer "an Anthropic experiment" — it is the de facto standard for exactly this job:

- Introduced by Anthropic in **November 2024**, then adopted by **OpenAI (Mar 2025), Google/DeepMind, Microsoft (Copilot Studio, VS Code, Windows, Azure AI Foundry), AWS (Bedrock AgentCore)**.
- **December 2025:** donated to the **Agentic AI Foundation under the Linux Foundation** (co-founded with Block and OpenAI; AWS, Google, Microsoft, Cloudflare, GitHub, Bloomberg as members) — so the "single-vendor" objection is gone.
- Roughly **10,000+ public MCP servers** and **~97M monthly SDK downloads** at the end of 2025, growing since.
- The **2026-07-28 spec** is the largest revision so far: stateless protocol core (no session handshake), Extensions framework, Tasks, MCP Apps (tools that return UI), hardened authorization.
- Even the **NSA published security guidance describing MCP as "the de facto standard"** for connecting AI to external services.

The second half of the standard answer is **RAG**: when "talk to any data" means a *corpus* (thousands of PDFs, a wiki, a mailbox) rather than *an API*, the standard is embed + retrieve + put the retrieved chunks in context — not one tool call per document. MCP itself now has a Resources primitive for exposing data, but retrieval quality still usually comes from a vector index.

**Verdict by scenario:**

| "Talk to any data" means… | Standard method |
|---|---|
| Call an action in a system (create issue, send mail, query a DB) | **MCP server** (universal) or function calling against a REST API (usual for your own first-party services) |
| Read a large unstructured corpus | **RAG** (embeddings + retrieval), often *served through* an MCP resource |
| Read the user's own small files | **Workspace files / uploads** — what this app already does |

---

## 4. So: right or wrong?

- **Right:** the agent loop, the tool-schema injection, per-session sandboxed files, letting the model decide when to call a tool, and showing the call in the transcript. All standard.
- **Wrong-ish — one thing:** treating a hand-written per-service REST wrapper as *the* connector mechanism. That does not scale and it is not what "connector" means in 2026; it's a private catalog wearing a standard's name.
- **Already partly fixed:** `MCPStdioClient` / `MCPHttpClient` exist and route properly, so the standard path is present — it's just presented as the exotic option ("Add MCP server") instead of the default one.

### Cheapest correct refactor (no rewrite)

1. **Rename the mental model, not the code:** present built-ins as *"Built-in connectors (bundled REST)"* and MCP as *"MCP servers — the open standard"*. That alone makes the UI honest.
2. **Make MCP the primary add path.** The Add-connector dialog should take a URL/command and discover tools — which it already can.
3. **Freeze the built-in catalog.** No new hand-written REST connectors; new services arrive as MCP servers. Keep the 12 built-ins because they make the demo work offline with no install.
4. **Protocol currency:** pin to the stateless 2026-07-28 semantics when you touch `mcp_client.py` (drop reliance on session ids; keep the legacy HTTP+SSE path as a fallback, since it is deprecated but still common).
5. **Add retrieval only when the data is a corpus.** Until then, uploads + shell (`grep`, `python3`) genuinely beats a bolted-on vector store for phone-sized workloads.

---

## 5. One-line summary to remember

> Function calling is how the model *decides*; MCP is how the world *describes itself* to the model; RAG is how a corpus *fits* in the context window. This app does the first correctly, the second half-correctly, and skips the third on purpose.

---

### Sources

- Anthropic, *Introducing the Model Context Protocol* (Nov 2024) — https://www.anthropic.com/news/model-context-protocol
- Wikipedia, *Model Context Protocol* (adoption, 2026-07-28 revision) — https://en.wikipedia.org/wiki/Model_Context_Protocol
- MCP blog, *The 2026-07-28 Specification* — https://blog.modelcontextprotocol.io/posts/2026-07-28/
- WorkOS, *Everything your team needs to know about MCP in 2026* (AAIF/Linux Foundation donation, Dec 2025) — https://workos.com/blog/everything-your-team-needs-to-know-about-mcp-in-2026
- ChatForest, *The MCP Ecosystem in 2026* (server counts, platform support, spec history) — https://chatforest.com/guides/mcp-ecosystem-2026-state-of-the-standard/
- NSA, *Model Context Protocol (MCP): Security Design Considerations* (May 2026) — https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf
