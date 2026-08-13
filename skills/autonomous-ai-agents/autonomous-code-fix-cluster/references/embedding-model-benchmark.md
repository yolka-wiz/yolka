# Embedding model selection under 2 CPU / <2 GB RAM (measured 2026-08-10)

Goal constraint: embedding must fit ~2 CPUs and <2 GB peak RAM, run locally,
no API key. Measured on this box (8 vCPU, both models capped at 2 threads,
300 short chunks, fresh process per model, peak RSS via `ru_maxrss`).

## Results

| Model | Dim | Size | Peak RSS @2 thr | Speed @2 thr | Runtime |
|---|---|---|---|---|---|
| **BAAI/bge-small-en-v1.5** (fastembed) | 384 | 67 MB | **~466 MB** | **137 chunks/s** | fastembed only, no torch |
| sentence-transformers/all-MiniLM-L6-v2 | 384 | 90 MB | ~0.5–1.3 GB | 45 chunks/s | fastembed only |
| Qwen/Qwen3-Embedding-0.6B (sentence-transformers) | 1024 | 1.2 GB | **1,994 MB** (at the ceiling) | **2.4 chunks/s** | needs torch (~2 GB install) |

Verdict: bge-small-en-v1.5 is the default — it fits with 4× headroom, is 57×
faster than Qwen3 at 2 threads, and retrieval quality on descriptive queries
matches the use case (exact names are covered by the FTS5 keyword leg).

## Qwen3-Embedding-0.6B notes (why NOT on this constraint)

- **Not in fastembed** (checked latest 0.8.0 wheel — zero matches); requires
  sentence-transformers + torch, or a GGUF/llama.cpp path.
- **1024-d**: switching means `vec0 float[1024]` schema change + full re-seed.
- Peak RSS 1,994 MB ≈ the 2 GB ceiling with zero headroom for the rest of the
  stack — violates the constraint in practice.
- **32k context padding trap**: Qwen3-Embedding defaults to a 32k
  `max_seq_length`; without `model.max_seq_length = 512` every CPU forward
  pass pads to 32k tokens and takes minutes (a 258-chunk corpus never
  finished in 8 min). Cap it before benchmarking or using.
- Query-quality check was inconclusive without Qwen3's instruction-prompt
  format — another integration cost.

## Rules learned

- Swap models = change `EMBED_MODEL` (`.env`) + **re-seed all vectors**;
  never mix two models' vectors in one vec0 table (different vector spaces).
- Benchmark only until the resource verdict is clear — when RAM/speed already
  decide against a model, stop there; do not rabbit-hole into quality evals.
- fastembed model ids need the full HF id (e.g. `sentence-transformers/...`).
- One-time model download from HF direct egress works; cached after.
