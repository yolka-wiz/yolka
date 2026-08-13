# Qwen3-Embedding-0.6B vs BAAI/bge-small-en-v1.5 — measured benchmark (2026-08-08)

Context: choosing the embedding model for a sqlite-vec cross-agent memory over
the LibreOffice core repo (258 sampled chunks: module summaries + docs + symbol
maps). Target constraint: 2 CPU threads, <2 GB RAM. All numbers measured on an
8-vCPU / 11 GB container with the thread cap applied.

## Resource benchmark (2 threads, fresh process, 300 short chunks)

| Metric | bge-small-en-v1.5 | Qwen3-Embedding-0.6B |
|---|---|---|
| Load (warm cache) | 1.7 s | ~10-30 s (torch + 310 weight files) |
| Speed | **137 chunks/s** | **2.4 chunks/s** (57x slower) |
| Dim | 384 | 1024 |
| Peak RSS | **466 MB** | **1,994 MB** |
| Model download | 67 MB | 1.2 GB |
| Runtime | fastembed (ONNX) | sentence-transformers + torch (~2 GB install) |
| fastembed support | yes | **no** (0.8.0 wheel has zero Qwen3 matches) |

Cold-load note: first run included the HF download — Qwen3 load measured
568 s (mostly download), then 126 s to embed 300 chunks at 2 threads.

## Verdict

Qwen3-Embedding-0.6B sits essentially AT the 2 GB RAM ceiling with zero
headroom for the rest of the stack, is 57x slower, and drags in torch (or a
GGUF/llama.cpp path). For a 2-CPU / <2 GB budget, bge-small-en-v1.5 remains the
right default. Qwen3 only makes sense with more RAM, a GPU, or a quantized GGUF
serving path.

## Benchmark recipe (reproduce)

```python
import resource, time
from fastembed import TextEmbedding          # bge path
model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", threads=2)
# Qwen3 path:
#   import torch; torch.set_num_threads(2)
#   from sentence_transformers import SentenceTransformer
#   model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B"); model.eval()
#   model.max_seq_length = 512   # CRITICAL — see pitfalls
t0 = time.time(); vecs = list(model.embed(texts))
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
```

Always run each model in a SEPARATE fresh process, otherwise ru_maxrss is
cumulative across models and pollutes the comparison.

## Corpus quality spot-check (258 real chunks, same 3 queries)

bge-small-en-v1.5 (vector-only, top-1..3):
- "what language is libreoffice written in" -> README doc, then librelogo/libreofficekit symbols (weak-ish but plausible)
- "what is the sal module" -> static/sal/salhelper symbol chunks (misses the module summary)
- "system abstraction layer rtl osl" -> **repo:/sal module summary** + include/rtl/ustring.hxx (strong)

Qwen3 naive run (no instruction prefix) MISSED the sal module summary for
"system abstraction layer rtl osl" and returned unrelated symbol chunks —
worse than bge on the same corpus. Two causes identified:
1. tokenizer defaulting to 32k context made the run crawl (minutes per
   forward pass on CPU) until max_seq_length was capped;
2. Qwen3-Embedding requires its query-instruction prompt format for queries
   (document chunks embed without instruction; queries need the prefix).
Do NOT judge Qwen3 from a naive run — but do not adopt it on a <2 GB box
either; the resource verdict is decisive first.

## Lessons encoded

- fastembed 0.8.0: no Qwen3 support; full model ids required; `threads=` param
  caps ONNX intra-op threads (verified).
- sentence-transformers path: torch install ~2 GB; Qwen3 needs
  `model.max_seq_length = 512` for short chunks.
- vec0 table dim must match model (384 vs 1024) — schema change + full re-seed
  required when swapping models; never mix vectors from two models.
