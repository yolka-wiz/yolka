---
name: agno-agent-orchestration
description: "Use when provisioning agno/phidata agent fleets locally."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [agno, phidata, agents, mcp, sqlite-vec, playground, orchestration]
    related_skills: [mcp-server-verification, agent-workspace-provisioning]
---

# Agno Agent Orchestration

Build and run a local fleet of agno (or legacy phidata) agents that cooperate on
a codebase: shared cross-agent memory, web/library search via MCP, and a control
surface. Use when the user wants "a number of agents locally" for a repo,
indexing, or development support.

**Key version fact (verified 2026-08):** `agno` 2.8.x (the AgentOS rewrite) is the
successor of `phidata`. It natively ships MCP tools, SQLite session storage, and
OpenAI-compatible models — but **no Playground UI** and **no sqlite-vec vector
store** (only pgvector). Neither `phidata` 2.7.10 nor 2.6.x/2.5.x ever shipped
sqlitevec either (wheel-scanned). Plan for a custom sqlite-vec memory layer and a
small FastAPI control app.

## 1. Verify the model endpoint BEFORE wiring agents

OpenAI-compatible gateways reject wrong model ids and unexpected message roles.
Always probe first:

```bash
curl -s -H "Authorization: Bearer $KEY" $BASE_URL/models | python3 -c "import json,sys; print([m['id'] for m in json.load(sys.stdin)['data']])"
```

- Use the **exact model id** from `/models` (user shorthand often differs, e.g.
  `ds-v4-flash` vs the real `deepseek-v4-flash`).
- The opencode "Console Go" endpoint (`https://opencode.ai/zen/go/v1`) **rejects
  OpenAI's `developer` role** — agno's `OpenAIChat` maps `system`→`developer` by
  default. Fix in one place via `role_map` (see reference file for exact dict).

## 2. Wire the model (agno)

```python
from agno.models.openai import OpenAIChat
model = OpenAIChat(id=MODEL_ID, base_url=BASE_URL, api_key=KEY,
                   role_map={"system": "system", "user": "user",
                             "assistant": "assistant", "tool": "tool",
                             "model": "assistant"})
```

Requires `pip install openai`. Session persistence: `Agent(db=SqliteDb(db_file=...))`
— requires `pip install sqlalchemy`.

## 3. Cross-agent memory: build your own sqlite-vec layer

agno/phidata have no built-in sqlite-vec store. The lightweight pattern that works:

- `pip install sqlite-vec` — the extension + `sqlite_vec.load(conn)` (needs
  `conn.enable_load_extension(True)` before, `False` after).
- One shared SQLite file with: `vec0` virtual table for embeddings, FTS5 table
  for keyword search (sync via an `after insert` trigger), plus plain
  `facts` / `runs` / `index_meta` tables for agent-visible state.
- **KNN query gotcha:** sqlite-vec vec0 tables need BOTH
  `where vec.embedding match ? and k = ?` — omitting `k` gives
  "Incorrect number of bindings supplied" with a confusing 1-vs-2 message.
- `dict(row)` requires `conn.row_factory = sqlite3.Row`.
- Embeddings: `fastembed` (ONNX, no API key). **Model name needs the
  `sentence-transformers/` prefix** (`sentence-transformers/all-MiniLM-L6-v2`,
  384-d) — the bare `all-MiniLM-L6-v2` is not in fastembed's supported list.
- Expose store ops to agents as `@tool` functions bound to the agent name
  (`memory_add`, `memory_search` hybrid vec+fts, `memory_fact` get/set,
  `memory_stats`) — every agent gets the same tools, so memory is shared.

## 4. MCP tools (context7 etc.) are ASYNC-ONLY in agno 2.8

Passing a plain `MCPTools(...)` instance registers **zero tools**. Correct pattern:

```python
from agno.tools.mcp import MCPTools
from agno.tools.mcp.params import StreamableHTTPClientParams

async with MCPTools(transport="streamable-http",
                    server_params=StreamableHTTPClientParams(
                        url=CONTEXT7_URL,
                        headers={"Authorization": f"Bearer {KEY}"}),
                    tool_name_prefix="context7") as mcp:
    searcher = Agent(..., tools=[..., mcp])
    resp = await searcher.arun(message)
```

So the MCP-using agent must be built AND run inside the `async with`. Keep a
no-MCP variant for the sync Team path (still has web tools).

## 5. Agents + Team (agno 2.8)

- `Agent(name=, model=, db=, description=, instructions=, tools=, markdown=True)`.
- `Team(members=[...], mode="coordinate", db=...)` — **no `leader` kwarg** in 2.8;
  the Team itself is the coordinator. Route-by-instructions, not a leader param.
- Distinct roles work well: code inspector(s), searcher (web+MCP), indexer
  (memory+index owner). Give each agent the memory tools so findings propagate.

## 6. Control surface

agno 2.8 has no Playground UI (removed; AgentOS platform needs Docker/Postgres —
avoid for single-box lightweight setups). Build a ~100-line FastAPI app:
`GET /agents`, `POST /run {message, agent}`, `/memory/*`, `/runs`, plus a tiny
HTML chat page. Sync endpoints run in FastAPI's threadpool; for the async-MCP
searcher use `asyncio.run(...)` inside the sync handler.

## 7. Repo indexing pipeline (parallel-agent-ready)

1. `universal-ctags -R` → symbol index (LibreOffice core: 544k tags in ~10 s).
   - ctags writes **absolute paths** — make paths relative before bucketing by
     top-level module, or everything collapses into one `""` bucket.
   - `--languages=...,Shell` warns "Unknown language Shell" — harmless.
2. `ripgrep` for live search (already installed on this workspace).
3. Seed shared memory: per-module summary chunks (file counts, key files),
   README/docs chunks, per-module top-symbol chunks → embed → vec0.
4. Regenerate agent files (`AGENTS.md`, `REPO_MAP.md`, `MODULES.md`) from the
   index into the repo root — untracked generated files, structured H1+§s.
5. Keep `MAX_FILES_PER_MODULE` bounded — embedding the whole repo is not
   needed; sample key files, keep ctags exhaustive.

## Pitfalls

- `load_dotenv` does NOT override already-exported env vars — a stale `export`
  in the persistent shell silently wins. Use `load_dotenv(..., override=True)`
  when `.env` must be authoritative.
- scrapling (`pip install scrapling`) imports need `playwright` AND
  `browserforge` pip packages (browser binaries NOT required for static
  `Fetcher`; do not run `playwright install` — geo-blocked CDN).
- `duckduckgo-search` is renamed to `ddgs` (`from ddgs import DDGS`); old import
  still works but warns. DDG rate-limits datacenter IPs — fall back to
  `DDGS(proxy="socks5h://...")`.
- scrapling `Response` has `.status`/`.text`, not `.title`.
- Secrets: keep keys in `.env` (chmod 600, gitignored); never echo; never in
  memory or repos. Load via dotenv at runtime.

## Verification checklist

- `curl $BASE_URL/models` → model id exists
- One real agent run returns grounded answer citing repo files
- `memory_add` then `memory_search` returns the chunk (KNN distance sane)
- MCP agent run calls a real MCP tool (e.g. context7 resolve + query)
- FastAPI `/agents` and `/run` return 200
- Team run routes and answers

## References

- `references/agno-2.8-and-opencode-gotchas.md` — verified session details:
  endpoint behavior, exact import paths, wheel-scan evidence, SQL snippets,
  LibreOffice repo facts.
