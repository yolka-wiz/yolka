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

## Sizing on Apple Silicon (Mac, unified memory)

Rule of thumb: **quantized model ≈ half your free RAM** leaves room for OS +
KV cache + a concurrent embedding model. If the embedding model runs in a
**separate project** (never co-resident), size the LLM against nearly your full
free budget and go one rung bigger.

Two-model pattern (one per role, loaded ONE at a time — never both): on a 16GB
M4 with ~8GB free (plus ~3GB squeeze = ~11GB budget), a Q4_K_M model at
**~6.6 GB weights + ~2-3 GB KV** fits with headroom. Next rung (27B+/30B+)
needs 16-18GB for weights alone — ruled out.

**2026 agentic model landscape** (see `references/apple-silicon-agentic-models-2026.md`):
- Multi-purpose (needs multimodal): **Gemma 4 12B Unified Q4_K_M** (~6.6 GB, 26B-MoE-class
  quality, text+image+audio+video, 256K ctx, tool calling, Apache 2.0).
- **Text-only ONLY (no vision/audio needed) — skip multimodal Gemma, use Qwen.** The
  2026 consensus (r/LocalLLaMA + Gemma-4-vs-Qwen-3.5 writeups) is that **Qwen smalls beat
  Google's in their weight class on tool use/RAG**, and Gemma 4's vision/audio towers are
  wasted weight you pay for in file size + RAM. Multi-purpose: **Qwen3.5-4B** (~2.5 GB,
  in-class leader); Coding: **Qwen3.5-9B** (~6.6 GB, strongest under-10B agentic coder).
  Same family, text-only, consistent tooling.
- Smaller fallbacks: Gemma 4 E4B (4.5B eff), Qwen3.8-4B (fastest per-GB).
- **Context ceiling:** 12B @ Q4 caps ~16-32K ctx; for 128K+ drop to E4B or 9B.
  Keep `num_ctx` ≤ ~32K or the Mac swaps and tok/s collapses. Never load two
  LLMs simultaneously.

## Runtime on Apple Silicon: MLX beats llama.cpp for <14B models

For **models under ~14B params on a Mac**, MLX (`mlx-lm`, mlx-community weights) is
**20-87% faster than llama.cpp/GGUF** (measured: M4 Max Qwen3-4B 4-bit 525 vs 281 tok/s;
M2 Ultra Qwen2.5 ~230 vs ~150). Why: MLX is built for unified memory — zero-copy shared
arrays, lazy/fused Metal kernels. llama.cpp copies layers across the CPU/GPU boundary.
The gap collapses at larger models where memory bandwidth (not kernel efficiency) is the
bottleneck — so your 9B/12B picks are squarely in MLX's winning zone.

- **Use MLX** (`mlx_lm.generate` / `mlx_lm.server --port 8080`, OpenAI-compatible) with
  `mlx-community/<model>-4bit` weights when Mac-only, model <14B, max speed matters.
- **Use llama.cpp/GGUF** when: cross-platform portability (same file on Win/Linux),
  CPU fallback needed, long-context / barely-fits-RAM (layer offloading), or the model
  only ships as GGUF.
- **Pragmatic:** install both — MLX for the hot path, Ollama/llama.cpp for the long tail.
- **Layer overflow / offloading** (`llama.cpp -ngl N`): split model layers across
  GPU↔CPU so a too-big model still runs (slowly) — activations are copied at each
  boundary crossing. It's a compatibility/headroom feature, NOT a speed feature, and
  irrelevant when your model fits RAM (then everything sits on Metal). MLX has no
  overflow because unified memory needs none.
- Always measure BOTH runtimes on YOUR model + num_ctx before committing — the 20-87%
  gap is real but hardware/context dependent (base M4 is at the low end of the curve).

## Concurrency truth
**"many agents" ≠ parallelism on one local model** — Ollama serializes requests
per model. You can define many agents cheaply, but only one
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
