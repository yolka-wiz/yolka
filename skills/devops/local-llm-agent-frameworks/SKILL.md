---
name: local-llm-agent-frameworks
description: "Use when setting up or running local LLM agent frameworks."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [agents, llm, phidata, agno, ollama, orchestration, playground, local]
    related_skills: [hermes-web-tools, dev-toolchain-provisioning, agent-workspace-provisioning]
---

# Local LLM Agent Frameworks (phidata/agno + Ollama)

Use when the user wants to run agent frameworks **locally** to help develop software
faster: planning the stack, installing, sizing models, choosing orchestration, wiring
a control surface. Primary target: phidata/agno, but the sizing and orchestration
lessons generalize (CrewAI, LangGraph, etc.).

## The 4-layer stack (what "running phidata locally" actually needs)

1. **Framework** — `pip install phidata` (2.7.10, Py ≥3.7) or its successor
   `agno` (2.8.7, Py ≥3.9).
2. **LLM client** — `pip install ollama` is a **separate extra**, NOT pulled by
   phidata. `from phi.model.ollama import Ollama` raises ImportError without it.
3. **LLM runtime** — Ollama (local) OR any OpenAI-compatible server (vLLM,
   llama.cpp, LM Studio, remote GPU box) via `phi.model.openai.openai_like`.
4. **Control surface** — Playground UI (`localhost:7777`, FastAPI, sessions in
   local SQLite, no data leaves the box), REST (Agent-API template — needs
   Docker+Postgres), or plain Python `agent.run()` / `workflow.run()`.

## Rebrand pitfall (phidata → agno)

Project renamed Jan 2025 to **Agno** (repo `agno-agi/agno`). The `phidata` package
is still released but legacy; the two have **different import namespaces**
(`phi.*` vs `agno.*`). Decide one, PIN the version in the venv, never mix imports.

## Install on this Debian agent box (Aliyun mirror)

```bash
source ~/.bashrc
uv pip install phidata ollama          # into existing ~/workspace/agent-env
# verify:
python -c "from phi.agent import Agent; from phi.model.ollama import Ollama; print('ok')"
```

## Ollama reachability (geo-blocked env — verified 2026-08)

- `ollama.com` (installer/UI) blocked direct (**403**) → works via SOCKS5
  `curl -x socks5h://<host>:<port>`.
- `registry.ollama.ai` (model pulls) reachable direct — **404 on root is a valid
  response**, not a block; don't misread it as "registry down".

## Model sizing on a CPU-only box (the weak link)

Measured this container: **8 vCPU / 11 GiB RAM, no GPU, no Docker** (AGENTS.md may
claim 15 GB — trust `free -h`, not the docs file).

| Model (Q4) | Size | Speed on 8 vCPU | Verdict |
|---|---|---|---|
| qwen2.5-coder:3b | ~2 GB | ~10–15 tok/s | ✅ comfortable |
| qwen2.5-coder:7b-instruct | ~4.7 GB | ~4–8 tok/s | ⚠️ fits, slow |
| 14b+ | ≥9 GB | not viable | ❌ |

**Concurrency truth**: "many agents" ≠ parallelism on one local model — Ollama
serializes requests per model. You can define many agents cheaply, but only one
runs effectively at a time on a small local model. The pragmatic architecture for
fast dev loops is **hybrid**: phidata runs locally, agents point at a remote
OpenAI-compatible/cheap endpoint (DeepSeek, OpenRouter, remote GPU box); keep the
small local model only for offline/simple tasks.

## Orchestration (phidata's own guidance)

- **Agent Teams** (`team=[...]`) — leader delegates; docs explicitly warn they are
  "not reliable for complex tasks... need constant oversight".
- **Workflows** (subclass `Workflow`, logic in `run()`) — deterministic, stateful,
  cache results in SQLite via `session_state`; **recommended for production/dev
  pipelines**. Use for plan→code→review→test chains.

## Built-in software-dev tooling (no custom code needed)

`File`, `Shell`, `Python`, `Github`, `Jira`, `Linear` tools + knowledge bases
(Text/PDF/Website) for repo RAG + structured outputs + workflow caching.

## Verification steps (never report "installed" without these)

1. Import check (above).
2. Playground smoke test: `python playground.py` → `curl -s localhost:7777` returns
   HTML (or the provided URL in logs).
3. Model check: `ollama list` shows the pulled model before wiring agents to it.

## References

- `references/phidata-agno-2026.md` — verified versions, docs URL map, hardware &
  network measurements, model sizing detail, reachability probe results.
