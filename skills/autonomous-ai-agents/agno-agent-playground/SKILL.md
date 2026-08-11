---
name: agno-agent-playground
description: "Build agno agent fleets: sqlite-vec memory, MCP, FastAPI."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [agno, agents, sqlite-vec, mcp, playground, indexing, fastembed, opencode]
    related_skills: [mcp-server-verification, agent-workspace-provisioning, codebase-architecture-research]
---

# Agno Agent Playground

Build a fleet of agno agents over a large codebase (e.g. LibreOffice core):
two code inspectors, one web/library searcher (with context7 MCP), one
index/memory keeper — all sharing one sqlite-vec cross-agent memory, served by
a lightweight FastAPI control API, and orchestrated by a headless CLI.

Reference implementation: `/home/agent/workspace/playground` (LibreOffice core).

## 1. Stack decisions (verified 2026-08-08)

| Piece | Choice | Why |
|---|---|---|
| Framework | `agno[mcp]==2.8.7` (NOT phidata 2.7.10) | agno 2.8 natively ships MCP, SQLite sessions, OpenAI-compatible models. phidata 2.7.10 has NO MCP at all |
| Vector memory | **sqlite-vec** (`pip install sqlite-vec`) + custom layer | Neither agno 2.8 nor phidata ships sql-vec (agno 2.8 vectordb = pgvector only; phidata 2.7.10 = lancedb/pgvector/qdrant/...) |
| Embeddings | `fastembed` (ONNX, no torch, no API key) | `sentence-transformers/all-MiniLM-L6-v2`, 384-d, ~23 MB, HF reachable direct |
| Sessions | agno `SqliteDb(db_file=...)` | single-file persistence; requires `sqlalchemy` |
| Model | OpenAI-compatible endpoint (opencode/Console Go) | `OpenAIChat(id=..., base_url=..., api_key=...)` |
| UI | FastAPI app (agno 2.8 has NO Playground UI — removed in AgentOS rewrite) | Playground UI moved to heavy AgentOS (Docker+Postgres) |
| Search | `ddgs` (new package; old `duckduckgo-search` renamed) + `scrapling` + `curl_cffi` | verified direct egress; proxy fallback for rate limits |

## 2. opencode / Console Go endpoint quirks (IMPORTANT)

Base URL: `https://opencode.ai/zen/go/v1`

- **Model id is `deepseek-v4-flash`, NOT `ds-v4-flash`** — the short form gets
  `ModelError: Model ds-v4-flash is not supported`. List valid ids:
  `curl -H "Authorization: Bearer $KEY" $BASE/models`
- **Rejects OpenAI `developer` role** (`unknown variant 'developer'`). Fix in
  `OpenAIChat(role_map={"system":"system","user":"user","assistant":"assistant","tool":"tool","model":"assistant"})`.
  Setting `system_message_role="system"` on the Agent does NOT fix it — the
  role map lives in the model class (`agno/models/openai/chat.py`:
  `default_role_map = {"system": "developer", ...}`).
- Endpoint has NO `/embeddings` → use local fastembed for vectors.
- `load_dotenv(..., override=True)` — otherwise a stale exported env var
  (e.g. from `set -a && . ./.env`) silently wins.

## 3. agno 2.8.7 API facts (differs from phidata docs)

- `Agent(model, name, db, tools, description, instructions, markdown, debug_mode)`
- `Team(members=[...], mode="coordinate")` — **no `leader` kwarg**; the Team IS
  the coordinator. `mode="coordinate"` routes; members delegate via the team.
- `MCPTools` is **async-only**: tools register only inside
  `async with MCPTools(transport="streamable-http", server_params=StreamableHTTPClientParams(url=..., headers=...), tool_name_prefix=...) as mcp:`.
  Pass the entered instance to the Agent; run with `await agent.arun(...)`.
  Building `MCPTools(...)` without entering the context yields an agent with
  zero MCP tools (silent).
- `OpenAIChat`/`SqliteDb` require `pip install openai sqlalchemy` (not pulled
  by `agno[mcp]`).
- context7 MCP: `https://mcp.context7.com/mcp`, header
  `Authorization: Bearer ctx7sk-...` (key in .env, chmod 600, never commit).

## 4. sqlite-vec cross-agent memory pattern

Single SQLite file shared by ALL agents (see `memory_store.py` in the
reference playground):

```sql
create virtual table knowledge_vectors using vec0(embedding float[384]);
create table knowledge(id integer primary key autoincrement, text text, source text,
  agent text, kind text, created_at text default (datetime('now')));
create virtual table knowledge_fts using fts5(text, source, agent,
  content='knowledge', content_rowid='id');   -- FTS5 external content + trigger
create table facts(agent text, key text, value text, updated_at text, primary key(agent, key));
create table runs(id integer primary key autoincrement, agent text, task text, summary text, status text, ...);
create table index_meta(path text primary key, lang text, symbols int, lines int, mtime real);
```

Pitfalls (each cost a debug cycle):
- `sqlite3.connect(...)` then `conn.row_factory = sqlite3.Row` BEFORE using
  `dict(row)`.
- vec0 KNN **requires** the match clause: `where vec.embedding match ? and k = ?`
  (omit `limit`; k already bounds). Missing `match` → "Incorrect number of
  bindings".
- serialize vectors with `sqlite_vec.serialize_float32(vec)`.
- fastembed model name must be the full id: `BAAI/bge-small-en-v1.5` (384-d,
  67 MB) — lightest verified option: ~0.5 GB peak RSS and ~138 chunks/s at
  `threads=2` (measured); `sentence-transformers/all-MiniLM-L6-v2` also works
  (90 MB, ~45 chunks/s at 2 threads). Swap = change `EMBED_MODEL` + re-seed;
  never mix vectors from two models in one vec0 table.
- Embeddings are the slow path on CPU (~10-30 chunks/s); keep chunks sampled
  (per-module summaries + key files, not every file).

## 5. Tooling for a huge C++ repo

- universal-ctags: `ctags -R --languages=C,C++,Java,Python,Sh ...` — language
  name is **`Sh` not `Shell`** (unknown-language warning otherwise). LibreOffice
  core: 544k tags in ~10 s on 8 vCPU.
- ctags writes **absolute paths** with an absolute `-f` output on absolute
  input paths → always relativize before grouping by top-level module, or all
  symbols land in one `""`/`(root)` bucket.
- LibreOffice uses `.cxx`/`.hxx` (NOT `.cpp`) — count and index accordingly.
- ripgrep is already present; LSPs (clangd 19, pyright) install cleanly via
  apt/npm, but a full `compile_commands.json` needs a LO build (hours) — agents
  navigate with ctags/rg instead.
- scrapling needs `playwright` + `browserforge` Python libs at import time
  (NOT browser binaries — those are geo-blocked, don't `playwright install`).
- `ddgs` works direct; DuckDuckGo may throttle — fallback
  `DDGS(proxy="socks5h://192.168.4.120:10909", timeout=25)`.

## 6. Layout (reference)

```
playground/
├── .env                  # secrets (600, gitignored)
├── config.py             # model factory + role_map, paths, key check
├── memory_store.py       # sqlite-vec cross-agent memory + tool wrappers
├── playground.py         # FastAPI: /agents /run /memory/* /runs + chat page
├── orchestrate.py        # CLI: status | index | agent <name> | team | memory
├── agents/__init__.py    # 4 agents + Team + async run_searcher
├── tools/                # repo_tools, search_tools, index_tools
├── scripts/              # setup.sh (idempotent), index_repo.sh, seed_memory.py, build_agent_files.py
└── data/                 # lo_memory.db, agno_sessions.db, lo.tags
```

## 7. Verification checklist (do all before declaring done)

1. `uv pip install` all deps; import agno, sqlite_vec, fastembed, scrapling, ddgs, curl_cffi.
2. `OpenAIChat(id=..., base_url=..., api_key=...)` constructs; `/models` on the
   endpoint lists the id you chose.
3. One real agent run returns grounded content (not an API error).
4. `MCPTools` searcher: `asyncio.run(run_searcher("resolve harfbuzz via context7"))`
   returns docs — proves MCP + key + async pattern.
5. Memory store self-test: add → hybrid search returns the chunk.
6. Playground boots: `uvicorn playground:app --port 7777`; `GET /agents` 200.
7. Index pipeline: ctags → seed_memory → build_agent_files; REPO_MAP shows
   real per-module counts; no empty `""` module bucket.
8. Team run answers a repo question and cites real files.

## Pitfalls recap (fast scan)

- `ds-v4-flash` vs `deepseek-v4-flash` → check `/models` first
- `developer` role rejected → `role_map` on OpenAIChat
- MCPTools silent zero-tools → must be `async with`
- `dict(row)` needs `row_factory = sqlite3.Row`
- vec0 KNN needs `match ? and k = ?`
- fastembed needs full model id
- ctags `Sh` not `Shell`; relativize absolute paths
- `.cxx` not `.cpp` in LibreOffice
- `load_dotenv(override=True)` to beat stale exports
