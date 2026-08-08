# GUI architecture — how a desktop frontend consumes the albdf binary

Design thinking recorded 2026-08-05 at the user's request ("keep thinking about
the gui layer, just think how the gui is going to utilize this binary"). Full
note lives in the repo: `docs/research/004-gui-architecture.md` (uncommitted at
write time; fold into a docs commit when GUI work starts). This reference keeps
the decision framework accessible without re-deriving it.

## The central fork: library mode vs binary mode

| Mode | Shape | Latency | RTL complexity in GUI | Coupling |
|---|---|---|---|---|
| A. Library | GUI links `Pdf4QtLibCore` (engine survived M1 strip; widget layer did NOT — re-import `PDFViewerWidget` from upstream remote or build own canvas) | Best | High — GUI sees bidi/shaping internals | Tight C++/ABI |
| B. Binary | GUI spawns `albdf` per op (daemon mode later if needed); JSON in/out | 30–80 ms/op — fine for v1 | **Zero** — GUI sends text+coords, binary shapes | Loose, language-agnostic |

**Recommended: B — the CLI contract IS the API.** Reasons:

1. All RTL complexity (bidi, HarfBuzz, GPOS marks, ToUnicode, ActualText)
   stays in the tested headless core. GUI is RTL-agnostic: place text, show
   pixels.
2. Latency proven fine: 0.03 s/page render, 0.04 s search, 0.02 s delete at
   72 dpi. Debounce live preview.
3. Determinism = testability: every GUI behavior is reproducible headlessly
   against the same JSON the GUI consumes.
4. ADR-0002 stays intact — GUI lives in a separate repo; core repo stays lean.

Library mode remains the escape hatch for sub-second interactive shaping
(drag-to-place); the engine seam (lib + CLI from same sources) keeps that
additive.

## The #1 gap: no machine-readable output

All commands print human tables. GUI work starts with engine-side
`--json` (or `--format json`) across: info, render metadata, fetch-text /
recognize-text (with **item bboxes** for hit-testing), search-text (with
**match rects** for highlight overlays), form-list, and op results (exit
codes already exist — keep them, add JSON body). This is headless-testable
and unlocks every GUI shape. Geometry export (bboxes/rects) is the second
engine seam to preserve.

## GUI layer sketch (thin, KDE-friendly)

- Canvas: QML/QWidgets page view; PNG tiles via `albdf render` (spawn +
  cache); zoom = re-render at higher dpi.
- Edits: all ops call `albdf <op> --json` on a working copy; swap on success.
- Undo/redo: snapshot stack of the working PDF (ops are deterministic) or op
  log replay — no engine support needed.
- RTL editing: text field → debounced preview = add-text to throwaway page +
  render → commit. GUI never shapes.
- KDE: Wayland-safe (offscreen render only), KIO open/save, standard
  shortcuts.

## Milestones (when GUI work starts)

| M | Deliverable | Depends on |
|---|---|---|
| G1 | `--json` across commands + geometry export (engine, headless-testable) | — |
| G2 | Minimal viewer: open → render tiles → zoom/pan → fetch-text overlay | G1 |
| G3 | Edit ops: add-text (incl. RTL), delete-object, search-highlight, snapshot undo | G1 |
| G4 | Forms/sign UX + KDE packaging | G1–G3 |

## Self-critique (cloud-eng lens, per user preference)

| Severity | Issue | Mitigation |
|---|---|---|
| HIGH | Spawn-per-op rewrites the working file each edit; typing-preview lag if ops exceed ~100 ms | Debounce preview; defer daemon mode (YAGNI) until a real GUI measures it |
| MED | JSON protocol is a new public API with versioning burden; two output formats to keep consistent | Pin schema in docs; both formatters feed from same data structures |
| MED | Snapshot undo is O(files) — fine for small docs, not 1000-page books | Cap snapshot count; revisit if needed |
| LOW | Library mode abandoned → future sub-second interactions need widget re-import | Upstream remote still has widgets; known path |
| LOW | Two repos, one contract — divergence risk | CI runs GUI contract tests against the CLI in both repos |

## User-supplied test corpus convention

User-provided real-world PDFs for testing (e.g. 318.pdf Persian financial,
final.pdf Foxit Persian) go in `/home/agent/workspace/testing-temp/` with a
`README.md` manifest — NOT into `src/tests/fixtures/` (repo fixtures stay
OFL-only per repo AGENTS.md; user documents are not committed). Memory notes
the corpus location. When a compat sweep runs, use this corpus plus the
committed fixtures.
