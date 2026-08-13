# phidata / agno — verified facts & measurements (2026-08-08)

Research snapshot from the "what do we need to run phidata agents locally" session.
All items below were verified live, not copied from marketing.

## Versions & packaging (PyPI, checked 2026-08-08)

| Package | Latest | requires_python | Status |
|---|---|---|---|
| `phidata` | 2.7.10 | `<4,>=3.7` | legacy name, still released |
| `agno` | 2.8.7 | `<4,>=3.9` | successor ("The programming language for agentic software") |

- Project rebranded phidata → **Agno** in Jan 2025; repo `agno-agi/agno`.
  `agno-agi/phidata` repo still exists with a banner pointing to agno.
- Namespaces differ: `phi.*` (phidata) vs `agno.*` (agno). Don't mix.
- Docs: docs.phidata.com still live, **Mintlify** — every page available as
  `https://docs.phidata.com/<path>.md` and full index at
  `https://docs.phidata.com/llms.txt`.

## Verified install (Debian 13 agent box, Aliyun mirror)

```bash
uv venv /tmp/phi-venv && uv pip install --python /tmp/phi-venv/bin/python phidata
```
→ exit 0, installs clean from Aliyun PyPI.

Import gotcha verified:
```python
from phi.agent import Agent                      # OK
from phi.model.ollama import Ollama              # ImportError: `ollama` not installed.
```
Fix: `pip install ollama` (docs: `pip install -U ollama phidata`).

## Network reachability probes (geo-blocked env, 2026-08-08)

| URL | direct | via socks5h://192.168.4.120:10909 |
|---|---|---|
| https://ollama.com | **403** (blocked) | **200** ✅ |
| https://registry.ollama.ai | **404** (valid resp — registry is reachable) | 000 (proxy can't reach) |

Interpretation: installer/UI downloads need the SOCKS5 proxy; model pulls
(registry.ollama.ai) go direct. A 404 on a service root is NOT a block.

## Hardware (measured, this container)

- 8 vCPU; `free -h` → **11 GiB** total (~8.3 free at idle); no `/dev/nvidia*`;
  no docker binary. AGENTS.md claimed 15 GB — measured value wins.

## Local model sizing (CPU-only, Q4 quantizations, rough but useful)

| Model | Size | Est. speed on 8 vCPU | Fit |
|---|---|---|---|
| qwen2.5-coder:3b | ~2 GB | 10–15 tok/s | yes, comfortable |
| qwen2.5-coder:7b-instruct | ~4.7 GB | 4–8 tok/s | fits, slow |
| 14b+ | ≥9 GB | — | not viable on 11 GiB |

- Ollama serves requests per-model; concurrent agents queue on the same model
  (parallel contexts need more RAM via OLLAMA_NUM_PARALLEL). "Many agents" locally
  = serialized, unless the LLM endpoint is remote with real concurrency.

## Framework capabilities (from docs.phidata.com)

- Control: Playground UI = FastAPI app, default `localhost:7777`, sessions in local
  SQLite ("no data is sent to phidata"). Agent-API template = FastAPI + Postgres,
  needs Docker (absent on this box). Python API: `agent.run()` returns
  `RunResponse` (content, run_id, session_id, metrics, messages); `stream=True`
  yields `Iterator[RunResponse]`.
- Orchestration: **Teams** (`Agent(team=[...])`, leader delegates) — docs warn
  open-ended teams are "not reliable for real-world problems... need constant
  oversight... use Workflows for production". **Workflows** (subclass `Workflow`,
  implement `run()`) — deterministic, stateful, cache via `session_state` +
  `SqlWorkflowStorage` (sqlite).
- Software-dev tools shipped: File, Shell, Python, Github, Jira, Linear (+ web:
  DuckDuckGo, Newspaper4k, HackerNews, Firecrawl, etc.). Knowledge bases: Text,
  PDF, Website, CSV, JSON, Docx, Wikipedia, Arxiv... Vector DBs: pgvector, Qdrant,
  ChromaDB, LanceDB, Pinecone; storage: sqlite, postgres, yaml/json.
- Local/cheap model providers: `phi.model.ollama.Ollama`; OpenAI-compatible
  servers via `phi.model.openai.openai_like` (covers vLLM, llama.cpp, LM Studio,
  remote GPU boxes); OpenRouter, DeepSeek, Groq, Together, etc. all have modules.

## Recommended architecture for dev-speedup on this box

1. venv + `pip install phidata ollama` (Aliyun mirror OK).
2. Playground with 3 agents: coder (Shell/Python), reviewer (Github), researcher
   (DuckDuckGo/Newspaper4k) + SQLite storage.
3. One Workflow: plan → code → review, cached.
4. Hybrid LLM: remote OpenAI-compatible endpoint for speed; local qwen2.5-coder:3b
   as offline fallback. Code doesn't change when swapping model.
