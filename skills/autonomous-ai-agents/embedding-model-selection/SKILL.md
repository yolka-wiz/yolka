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
