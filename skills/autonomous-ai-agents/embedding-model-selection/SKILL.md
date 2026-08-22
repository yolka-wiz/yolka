---
name: embedding-model-selection
description: "Pick embedding models for vector memory at CPU/RAM limits."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [embeddings, fastembed, sentence-transformers, sqlite-vec, rag, benchmark, onnx]
    related_skills: [agno-agent-playground, agent-workspace-provisioning]
---

# Embedding Model Selection

Choose and benchmark embedding models for local vector memory (sqlite-vec,
RAG knowledge bases, agent memory) when the target box is resource-constrained
(e.g. 2 CPU cores, <2 GB RAM). The decision procedure below was validated on
real measurements (2026-08-08); numbers are in the reference file.

## Defaults by integration path

- **agno / fastembed / vector-DB path**: **nomic-embed-text v1.5** (768-d, ~274MB,
  Apache 2) is the default — fastembed + Ollama native, tiny, fast on CPU.
  fastembed (v0.8.0) does NOT support Qwen3 embeddings, so Qwen3-Embedding needs
  torch/GGUF as a heavier install.
- **Multilingual corpus**: **BGE-M3** (1024-d, MIT) — best open MTEB + multilingual,
  but ~2+GB; only if non-English RAG matters.
- **New 2026 on-device option worth testing**: **EmbeddingGemma** (308M, 768→128
  Matryoshka, Gemma license, runs on CPU).
- **<2GB budget / max speed**: **BGE-small-en-v1.5** (384-d, ~0.5GB) — the measured
  default below.

## Decision procedure (in this order)

1. **List what the runtime supports first.** fastembed: `TextEmbedding.list_supported_models()`
   — note model ids are FULL ids (`BAAI/bge-small-en-v1.5`, not `bge-small-en-v1.5`).
   fastembed 0.8.0 has NO Qwen3 support (grep the wheel: zero matches). If your
   candidate isn't supported, that means torch or GGUF/llama.cpp — factor the
   install cost in.
2. **Measure resource fit BEFORE quality.** In a fresh process (so peak RSS is
   not polluted by other models), embed your real chunk corpus at the target
   thread cap. Report: load time, chunks/s, peak RSS (`resource.getrusage(...).ru_maxrss`),
   dim. fastembed: `TextEmbedding(model_name=..., threads=N)`; sentence-transformers:
   `torch.set_num_threads(N)`.
3. **If the resource verdict is decisive, STOP.** Do not chase quality
   benchmarks once the model clearly violates the RAM/CPU budget — the user
   prefers decisive resource-driven decisions over long benchmark quests.
4. **Quality spot-check on YOUR corpus** (not MTEB): embed the real chunks,
   run 3-5 queries you actually use, compare top-k recall between candidates.
   Watch for the recall trap below.
5. **Swap safely**: change `EMBED_MODEL`, then FULL re-seed — never mix vectors
   from two models in one vec0 table (different vector spaces → garbage KNN).

## Measured numbers (2 threads, fresh process, 300 short chunks)

| Model | Dim | Peak RSS | Speed | Notes |
|---|---|---|---|---|
| **BAAI/bge-small-en-v1.5** | 384 | **~0.5 GB** | **137 chunks/s** | default choice for <2 GB boxes; also better retrieval than MiniLM |
| sentence-transformers/all-MiniLM-L6-v2 | 384 | ~0.5-0.7 GB | 45 chunks/s | fallback; slower |
| Qwen/Qwen3-Embedding-0.6B | 1024 | **~1.99 GB** | **2.4 chunks/s** | at the RAM ceiling, 57x slower, needs torch |

Verdict pattern: on a 2-CPU / <2 GB budget, big models sit at the ceiling with
no headroom for the rest of the stack — stay with a 384-d small model.

## When RAM is NOT the binding constraint (embedder runs in its own project)

The "<2 GB" rule applies only when the embedder shares a box with an LLM/other
stack. If it runs in a **separate project / separate slot** (user said so
explicitly — never shares RAM with the LLM), pick for QUALITY, not size. In that
case the best agno/fastembed-supported choice is:

- **mixedbread-ai/mxbai-embed-large-v1** ⭐ — 1024-d, 0.64 GB, Apache 2.0. Best
  quality-per-footprint in fastembed's supported list; top English retrieval.
  Wiring: `FastEmbedEmbedder(id="mixedbread-ai/mxbai-embed-large-v1")`.
- Close rival: `BAAI/bge-large-en-v1.5` (1024-d, 1.2 GB, MIT). Mid option:
  `nomic-embed-text-v1.5` (768-d). Only fall back to bge-small if budget returns.
- fastembed still has NO Qwen3 support (verified 2026) — Qwen3-Embedding is the
  MTEB leader but needs torch/GGUF and is the slow CPU path, so it's NOT the
  agno fit. mxbai-large is the best quality that plugs in natively.
- **mxbai query-instruction trap**: queries need the prefix
  `Represent this sentence for searching relevant passages: {query}`;
  documents embed bare. Skipping it silently degrades retrieval.
- **Dim must match**: mxbai is `float[1024]`, not 384. If you previously indexed
  with bge-small/nomic, FULL re-seed (never mix models in one vec0 table).
- Full fastembed supported list (dims/sizes/licenses): qdrant.github.io/fastembed/examples/Supported_Models/
  — top English dense by size: bge-small-* (384), arctic-embed-xs/s, all-MiniLM-L6-v2,
  nomic v1.5-Q (768), bge-base-v1.5 (768), arctic-embed-m (768), nomic v1.5 (768),
  mxbai-large (1024), arctic-embed-l (1024), bge-large-v1.5 (1024), multilingual-e5-large (1024).

## Pitfalls

- **Qwen3-Embedding tokenizer defaults to 32k context.** sentence-transformers
  pads every input to the model's configured max length; on CPU each forward
  pass takes minutes. Cap `model.max_seq_length = 512` for short chunks.
- **Qwen3-Embedding needs its query-instruction prompt format** for proper
  retrieval. Embedding queries without the instruction prefix degrades recall
  badly (observed: missed obvious hits that bge-small found). Document chunks
  embed without instruction; QUERIES need the instruction prefix.
- **vec0 dimension must match the model.** `float[384]` table + a 1024-d model =
  failure. Dim change requires recreating the virtual table + full re-seed.
- **Embeddings are the slow path on CPU** — keep the corpus sampled
  (summaries + key files), not every file.
- **Fastembed `threads=` param caps ONNX intra-op threads** — verified it
  actually limits CPU usage; pair with OMP_NUM_THREADS if a parent tool sets it.
- **HF model cache** lives in `~/.cache/huggingface` (1.2 GB for Qwen3) — purge
  if the model is abandoned; harmless to keep otherwise.

## Verification

- Fresh-process RSS at the target thread cap is the number that matters.
- Re-run the quality spot-check after the swap with the same queries you used
  before — recall should be equal or better; if it regressed, the swap isn't a
  win even if MTEB says otherwise.

## Reference

- `references/qwen3-vs-bge-benchmark.md` — full measured table, benchmark
  recipe (fastembed vs sentence-transformers), and the corpus spot-check.
