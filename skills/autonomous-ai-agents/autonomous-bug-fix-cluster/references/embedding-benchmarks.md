# Embedding benchmarks under a 2 CPU / <2 GB budget (measured 2026-08)

## Results (threads=2, 300 short chunks, peak RSS, fresh process)

| Model | Dim | Size | Peak RSS | Chunks/s | Notes |
|---|---|---|---|---|---|
| **BAAI/bge-small-en-v1.5** | 384 | 67 MB | ~466 MB | 137 | **winner** — smaller + faster + better retrieval than MiniLM |
| sentence-transformers/all-MiniLM-L6-v2 | 384 | 90 MB | ~0.5–1.3 GB | 45 | works, slower |
| Qwen3-Embedding-0.6B | 1024 | 1.2 GB | ~1,994 MB | 2.4 | AT the 2 GB ceiling, 57× slower; needs torch |

Decision rule under the budget: bge-small-en-v1.5. Swap = change `EMBED_MODEL`
+ re-seed; never mix vectors from two models in one vec0 table.

## Qwen3 gotchas (if ever revisited)

- fastembed 0.8.0 has NO Qwen3 support (checked the wheel; latest version).
  Use sentence-transformers (torch) or a GGUF/llama.cpp path.
- sentence-transformers trap: Qwen3 tokenizer defaults to 32k context; CPU
  padding makes every forward pass take minutes. Set
  `model.max_seq_length = 512` (chunks here are short).
- Qwen3 needs its query-instruction prompt format for good retrieval — naive
  `encode(query)` gave poor recall on real data.
- The opencode endpoint has no `/embeddings` (probed: no embedding models
  listed, endpoint 404s) — local ONNX is the only lightweight path.
