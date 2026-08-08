# M10 wave-2 CLI fuzz harness (DB #30) — build, verify, findings

Built 2026-08-06 on branch `m10/infra-fuzz` (commits 8d935a1 feat,
4726c93 ci, c234512 docs). Harness: `scripts/fuzz.sh` at the repo root.
Baseline run: 527 ops (50 iterations) ≈ 2 min, exit 1 due to findings below.

## Why a shell harness (not libFuzzer)

Plan constraint: deterministic script, no new language, no network/display,
default run under ~3 min, non-gating CI job. libFuzzer integration was
explicitly out of scope. Everything headless: `QT_QPA_PLATFORM=offscreen`
exported by the script itself.

## Architecture

- **Base corpus (5 docs):** `multipage` / `image-doc` / `overlap-text`
  regenerated via `src/tests/scripts/make-*.pdf.py` into the work-dir (never
  touching committed fixtures), plus committed `blank.pdf` and
  `test-baseline.pdf`. Generators are byte-deterministic; the harness
  `cmp -s` the regenerated files against committed fixtures →
  `generator_reproducible=yes|no` (warning only, not a failure).
- **Mutation manifest (python heredoc):** `random.Random(seed)` — Python
  documents the Mersenne Twister algorithm as stable across versions, so the
  corpus is reproducible on any platform. 10 types (dispatch `t =
  rng.randrange(10)`): truncate, zero-fill, bit flips (1..8), garbage header
  (random bytes or foreign magics `%!PS-Adobe-3.0`/`GIF89a`/PNG/PK/MZ),
  appended garbage, xor-region, empty file, junk-only file, self-concat,
  prepended junk. Each case records a `meta` string (e.g. `trunc=123`,
  `xor=9+100+42`) for debugging. Writes `corpus/m<i>.pdf` +
  `manifest.tsv` (`idx<TAB>path<TAB>base<TAB>type<TAB>meta`), parsed with
  `IFS=$'\t' read`.
- **Commands (10):** info, fetch-text, search-text (`<in> MULTIPAGE`),
  add-text, delete-object, delete-page, rotate, move-page, redact, render —
  argv built in `build_argv()`; write outputs go to unique paths under
  `out/`; render reuses one pre-created `out/render/` dir.
- **CLI-arg cases (~27):** fixed list, run on the valid generated multipage
  doc: unknown command, no args, no doc, oversized/negative/empty
  `--page`/`--page-select`/`--from`/`--to`/`--index`/`--angle`/`--text`/
  `--console-format`, empty search query, RTL add-text (`--lang fa --font
  fonts/NotoNaskhArabic-Regular.ttf`) and RTL search. Allowed exits `0 4 7`
  (observed: `info` with no doc → 4; unknown cmd / no args → 0; bad args → 7).
- **Classification (per case):**
  | exit | class | action |
  |---|---|---|
  | 124 / 137 (timeout kill) | HANG | finding; stops run at `--max-hangs` |
  | ≥ 128 (other signals) | CRASH | finding; run continues |
  | 0 / 4 / 7 on mutations | expected (contract) | recorded |
  | outside allowed set (CLI cases) | UNEXPECTED | recorded, not failed |
  | 125 / 126 / 127 | ERROR | harness error → abort |
  The CLI can legitimately return any nonzero on corrupt input per the
  exit-code contract (src/AGENT.md: 0 success, 7 invalid args; read errors 4);
  only signal deaths and timeouts are findings.
- **Determinism of the summary:** no timestamps, no durations; `failure=`
  lines use paths RELATIVE to the work-dir; `exit_histogram` keys sorted
  numerically. Two runs with the same seed in different work-dirs → byte-
  identical `fuzz-summary.txt` + identical `fuzz-cases.tsv` + identical
  corpus (verified).
- **Flags/env:** `--seed` (default 20260806) `--iterations` (50)
  `--binary` `--work-dir` `--timeout` (20) `--max-time` (0 = off)
  `--max-hangs` (3) `--keep`; env `ALBDF_FUZZ_SEED/ITERATIONS/TIMEOUT`.

## Verification recipes (proved the harness, not just the binary)

- **Detection machinery end-to-end without a real crash:** point `--binary`
  at a fake script — `kill -SEGV $$` → every case classifies CRASH (139),
  reproducers saved, exit 1; `sleep 30` + `--timeout 2` → HANG (124), stops
  at `--max-hangs 3` with `skipped=54` and a `note=` line; `exit 0` → PASS,
  exit 0. This satisfies the plan gate "verify the harness can detect a
  crash / the timeout path" honestly.
- **Determinism proof:** same seed, two different `--work-dir` paths →
  `diff` the three artifacts (summary, cases.tsv, corpus) — must be empty.
- **Masking gotcha discovered while bisecting F#1:** `render --page-first 0`
  with a MISSING output dir exits 7 (dir check precedes page handling), so
  an early probe looked clean; with `mkdir -p` the dir it SIGABRTs. Always
  satisfy prerequisites when probing for crashes.

## Findings (real, on VALID input; both in docs/PROBLEMS.md F#1/F#2)

- **F#1 CRASH — `render` out-of-range page numbers.** `albdf render
  doc.pdf --page-first 0 --page-last 1 --image-format png --image-res-dpi 72
  --image-output-dir <existing>` → exit 134. Stderr:
  ```
  Qt Concurrent has caught an exception thrown from a worker thread.
  This is not supported, exceptions thrown in worker threads must be
  caught before control returns to Qt Concurrent.
  terminate called after throwing an instance of 'std::out_of_range'
    what():  vector::_M_range_check: __n (which is 18446744073709551615) >= this->size() (which is 5)
  ```
  `18446744073709551615` = `(size_t)-1`: page 0 → unchecked `page-1` decrement;
  `--page-last 999999999` trips the same `at()` check in a worker. Bisect:
  `--page-first 0` crashes for ANY `--page-last` (even 1); `--page-last
  999999999` crashes with valid `--page-first`; `--page-first -1` → 7
  (validator catches negatives).
- **F#2 HANG — extreme DPI.** `--image-res-dpi 10000`+ never completes
  (dpi 10000 on 612×792 pt ≈ 85k×110k px; 999999 ≈ 94 GP). `dpi 0` / `-72`
  → exit 0 (degenerate but harmless). No size sanity check before allocation.
- **Non-findings (robust):** all 500 mutation cases (5 base docs × 10 types
  × 10 commands) exited with contract codes only (baseline histogram:
  `0:166, 4:321, 7:37`), zero crashes — parser and library handle malformed
  bytes cleanly.

## CI job (mirrors `benchmark`)

`.github/workflows/ci.yml` `fuzz` job: `continue-on-error: true`,
setup-toolchain, `ci/run-ci.sh --skip-asan --skip-format`, then
`bash scripts/fuzz.sh --iterations 200 --max-time 240 --work-dir
"$RUNNER_TEMP/albdf-fuzz"`, artifact upload (`if: always()`,
`if-no-files-found: ignore`) of `fuzz-summary.txt`, `fuzz-cases.tsv`, `fail/`.

## Extending the harness

- New command: append to `CMDS` array + `build_argv()` branch (keep argv
  shapes from `albdf <cmd> --help`).
- New abusive-arg case: `cli_*` branch in `cli_case()` + id in `CLI_IDS`
  (allowed exits are the 2nd arg of the `cli_case` call).
- New mutation type: add a branch in the python heredoc using ONLY `rng`
  (determinism), keep `t = rng.randrange(10)` dispatch (types 0..9), bump
  `mutation_types=` in the summary block.
- New fixture: it joins the corpus only via a `make-*.pdf.py` generator +
  `bases` list entry; the `generator_reproducible` hash check then covers it.
