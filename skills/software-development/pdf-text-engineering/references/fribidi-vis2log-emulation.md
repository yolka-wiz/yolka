# FriBidi vis2log emulation — visual→logical inversion (verified 2026-08-07)

Context: WS-C (GUI clipboard copy path) needed to re-invert RTL selections from
VISUAL order (`مالس` for `سلام`) to LOGICAL order. The task brief suggested
"apply the FriBidi vis2log step" — **that function does not exist in the
vendored FriBidi 1.0.16** (removed in the 1.0 series; the source tarball only
has `TODO: Explore vis2log`). This file is the verified replacement recipe.

## Available FriBidi 1.0.16 API (what you can actually call)

- `fribidi_log2vis` (logical→visual, SHAPES Arabic into presentation forms)
- `fribidi_get_bidi_types`
- `fribidi_get_par_direction` / `fribidi_get_par_embedding_levels_ex`
- `fribidi_reorder_line`

Headers/libs: core links FriBidi via `pkg_check_modules(FRIBIDI ...)` +
`PkgConfig::FRIBIDI` (src/CMakeLists.txt:53, Pdf4QtLibCore/CMakeLists.txt:211).
The header lives in the manifest-mode tree INSIDE the build dir:
`src/build/vcpkg_installed/x64-linux/include/fribidi/` (NOT the global
`vcpkg-cache/vcpkg/installed/` — the global tree lacks it).

## Emulation recipe (verified byte-for-byte)

```cpp
fribidi_get_bidi_types(visual, len, bidiTypes);
FriBidiParType base = FRIBIDI_PAR_ON;                       // auto-detect
FriBidiLevel maxLevel = fribidi_get_par_embedding_levels_ex(bidiTypes, NULL, len, &base, levels);
if (maxLevel == 0) return visual;                           // pure LTR / error
for (i = 0; i < len; ++i) positionsLToV[i] = i;             // CRITICAL: identity init
fribidi_reorder_line(FRIBIDI_FLAGS_DEFAULT, bidiTypes, len, 0, base, levels, NULL, positionsLToV);
logical[i] = visual[positionsLToV[i]];
```

Why it works: the L2/L3 reorder permutation is its own inverse for a string's
own levels, so reordering the VISUAL string with the VISUAL string's
types/levels recovers the logical order. `visual_str` may be NULL; the map is
still written.

## THE TRAP: reorder_line's map is input+output

First attempt passed an uninitialized map → the call returned success (ret 2)
but the map was never populated with sane values → output collapsed to the
repeated first char. The L2 loop does `index_array_reverse(map + a, n)` — it
PERMUTES whatever is in the array. Identity-init is mandatory.

## Verified behavior (probe linked against the build's libfribidi.a)

| visual input | logical output |
|---|---|
| `مالس` | `سلام` |
| `اببحرم` | `مرحبا` |
| `םולש` | `שלוּם` |
| `123 مالس` | `سلام 123` |
| `abc مالس def` | `abc سلام def` |
| `Hello world` | `Hello world` (passthrough) |

Round-trip: `vis2log(log2vis(L)) == L` — Arabic comes back in presentation
forms (log2vis SHAPES; the reorder is order-correct). Search already handles
this with a second NFKC pass (R#3). Copy must NOT normalize — users want the
text verbatim.

## albdf engine extraction facts (empirical, `albdf fetch-text`)

- `سلام` → `مالس`; `السلام` → `مالسلا`; `שלום` → `םולש`; `مرحبا` → `اببحرم`
  (pure RTL = clean character reversal, no multi-char ligature clusters in
  practice despite the ActualText comment claiming otherwise).
- `سلام 123` → `مالس123` (docstrum Layout flow DROPS the space between runs);
  the GUI per-character path (PDFTextLayout) keeps it: `مالس 123`.
- `abc سلام def` → `abc مالس def` (LTR runs in logical order, RTL run reversed
  in place).
- The engine emits runs in LOGICAL run order with each RTL run reversed in
  place — NOT standard bidi visual order (which would move a trailing EN run
  leftmost for RTL base).

## Design tension (decided: faithful vis2log)

- OUR engine's multi-run output (e.g. visual `مالس 123`, true logical
  `سلام 123`): segment-reversal would be correct, but vis2log returns
  `123 سلام` (bidi run reordering per auto-detected RTL base).
- FOREIGN standard-visual PDFs (digits leftmost for RTL base, e.g. visual
  `123 مالس`): vis2log is correct (`سلام 123`), segment-reversal is wrong.
- Chosen: faithful vis2log — standard bidi semantics, correct for the
  dominant real-world case (foreign PDFs) and for single-run RTL (the
  gui-rtl.pdf fixture); consistent with search's symmetric log2vis treatment.
  Single-run RTL is identical under both approaches.
- Corollary: table-extract CSV copy (per-cell inversion) is NOT trivially
  safe — a cell's isolated base-direction detection can reorder runs wrongly.
  Leave it unless the requirement is explicit.

## Probe methodology (reuse this, don't hand-simulate bidi)

Hand-simulating the bidi algorithm produced TWO wrong predictions this session;
a 20-line probe settled everything. Compile against the build's fribidi:

```bash
g++ -o probe probe.cpp \
  -I/home/agent/workspace/al-bdf-engine/src/build/vcpkg_installed/x64-linux/include/fribidi \
  /home/agent/workspace/al-bdf-engine/src/build/vcpkg_installed/x64-linux/lib/libfribidi.a
```

Write small UTF-8↔FriBidiChar (uint32 array) converters inline. Test both the
target case AND the round-trip `vis2log(log2vis(L)) == L` on mixed strings.
