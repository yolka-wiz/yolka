# Apple Silicon agentic model sizing — 2026 landscape

Researched 2026-08-13. Target: 16GB M4 Mac, ~8GB free (plus ~3GB squeeze =
~11GB effective budget). Embedding model lives in a separate project, so it
never shares RAM with the LLM.

## Sizing rules (Apple Silicon unified memory)

- **Quantized model ≈ half your free RAM** for comfort (OS + KV cache +
  concurrent embedder).
- If the embedder is in a separate project, size against ~full free budget and
  go one rung bigger.
- Q4_K_M model ≈ ~6.6 GB weights for 9-12B; + ~2-3 GB KV cache for 16-32K ctx.
  Fits in ~11GB with headroom.
- Next rung (27B / 30B MoE) needs 16-18GB for weights alone → ruled out.

## Two-model recommendation (one per role, loaded one at a time)

**Text-to-text only (no vision/audio) — the common case: use Qwen for BOTH.**
The 2026 consensus (r/LocalLLaMA + Gemma-4-vs-Qwen-3.5 comparisons) is that
Qwen smalls beat Google's in their weight class on tool use / RAG, and Gemma 4's
vision/audio towers are wasted file+RAM weight you never touch. Same family =
consistent chat template, no format friction.

| Role | Model | Q4 size | Notes |
|---|---|---|---|
| Multi-purpose | **Qwen3.5-4B** | ~2.5 GB | In-class leader for small text-only; fast; big headroom |
| Coding/agentic | **Qwen3.5-9B** | ~6.6 GB | Strongest under-10B agentic coder; verified OpenCode/Claude-Code backend; ~32K ctx |

If you DO need multimodal (image/audio/video), swap multi-purpose to
**Gemma 4 12B Unified** `Q4_K_M` (~6.6 GB, 26B-MoE-class quality, 256K ctx,
Apache 2.0). One model for both roles → just use Qwen3.5-9B for everything.

Install: `ollama run qwen3.5:4b` / `ollama run qwen3.5:9b` — or MLX weights
`mlx-community/Qwen3.5-9B-4bit` for the <14B speed win.

## Runtime: MLX vs llama.cpp on Apple Silicon

For **models <14B** MLX is **20-87% faster** than llama.cpp/GGUF (measured):

| Hardware | Model | MLX | llama.cpp | Advantage |
|---|---|---|---|---|
| M4 Max (128GB) | Qwen3-4B 4-bit | 525.5 tok/s | 281.5 tok/s | MLX +87% |
| M2 Ultra (192GB) | Qwen2.5 family | ~230 tok/s | ~150 tok/s | MLX +53% |
| M4 Max / Studio | 7B optimized (arXiv:2511.05502) | ~230 tok/s | not reached | MLX |

- MLX = Apple's array framework built FOR unified memory: zero-copy shared
  arrays, lazy/fused Metal kernels. llama.cpp copies activations across the
  CPU/GPU boundary → pure waste for memory-bandwidth-bound inference.
- **Gap collapses at larger models** (memory bandwidth, not kernel efficiency,
  becomes the bottleneck) — so your 9B/12B picks sit in MLX's winning zone.
- Use **MLX** when Mac-only + <14B + max speed: `mlx_lm.generate`,
  `mlx_lm.server --port 8080` (OpenAI-compatible), `mlx-community/<m>-4bit`
  weights. mlx-community hosts Gemma 4 / Qwen3.5 / Llama 4 / DeepSeek / Phi
  pre-converted.
- Use **llama.cpp/GGUF** when: cross-platform (same file on Win/Linux/Android),
  CPU fallback needed, long-context / barely-fits-RAM, or model only ships as
  GGUF. It's the engine inside Ollama/LM Studio/Cursor/Continue.
- **Layer overflow / offloading** (`llama.cpp -ngl N`): splits model layers
  GPU↔CPU so a too-big model still runs slowly; activations are copied at each
  boundary crossing. A compatibility/headroom feature, NOT speed, and irrelevant
  when the model fits RAM (then all layers sit on Metal). MLX has no overflow —
  unified memory needs none.
- **Verify on YOUR box** before committing: base M4 sits at the low end of the
  memory-bandwidth curve, so measure both runtimes at your num_ctx.

## Other 2026 models considered

| Model | Params | Fit verdict |
|---|---|---|
| Gemma 4 E4B | 4.5B eff (8B w/embeds) | ✅ smaller fallback, multimodal |
| Gemma 4 E2B | 2.3B eff (5.1B w/embeds) | ✅ tiny, ~1GB QAT, runs anywhere |
| Qwen3.8-4B Distilled | 4B | ✅ fastest per-GB, big headroom |
| Qwen3.5-9B | 9B | ✅ the coding pick |
| Gemma 4 26B-A4B MoE | 26B total/4B act | ⚠️ file ~15GB, too big for 8GB weights |
| Qwen3.8-27B | 27B | ❌ needs 16GB+ |
| Muse Glimmer 30B | 30B | ❌ needs 18GB+ |
| Phi-4 Mini 3.8B / Llama 3.3-8B | — | not agentic/tool-use leaders; Llama 4 has 700M-MAU license cap |

Gemma 4 family: E2B, E4B, 12B Unified, 26B-A4B, 31B. Apache 2.0. PLE
(per-layer embeddings) makes E4B ~8GB loaded despite 4.5B effective — heavier
than a plain 4.5B. QAT checkpoints ship for all 5 sizes (~1GB for E2B).
Gemma 3→4 was the largest single-generation jump in open models (GPQA 42→84%,
AIME 20.8→89%, LiveCodeBench 29→80%), but that's the 31B; smalls still trail
Qwen.

## Context ceiling pitfall

12B @ Q4 caps ~16-32K ctx. For 128K+ drop to E4B or the 9B. Keep `num_ctx` ≤
~32K or the Mac swaps and tok/s collapses. Never load both LLMs simultaneously
(~13GB combined blows an 11GB budget).

## Sources

- HuggingFace blog: "Welcome Gemma 4" (2026-04-02) — sizes, PLE, KV cache, sizes.
- Unsloth docs Qwen3.8 — 27B/2.4T-A95B; 27B needs 16GB+.
- runaiathome Gemma 4 VRAM: 12B ≈ 6.6 GB Q4, E4B ≈ 8GB, 27B ≈ 14.9GB.
- ollama.com/library/qwen3.5:9b — coding-optimized Q4_K_M ~6.6GB, 32K ctx.
- llmhardware.io — 7-8B at 25-35 tok/s on Mac (Metal).
- ai.rs "Gemma 4 vs Qwen 3.5 vs Llama 4" (2026-04-02) — Gemma 4 bench jump; Qwen
  smalls lead Google's in-class.
- ai-stat.ru "Gemma 4 vs Qwen 3.5" (2026-04-05) — r/LocalLLaMA consensus: Qwen
  3.5 4B/0.8B significantly outrun Google's smalls on tool use/RAG; HLE gap
  favors Qwen on expert tasks.
- groundy.com / compute-market.com "MLX vs llama.cpp Apple Silicon" (2026) —
  MLX 20-87% faster <14B; layer-offload; arXiv:2511.05502 ~230 tok/s 7B.
