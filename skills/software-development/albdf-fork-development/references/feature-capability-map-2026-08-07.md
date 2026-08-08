# albdf feature-capability map — what the engine has vs what the CLI exposes

Status: audited 2026-08-07 (post-0.2.0). Source of truth for "how far are we
from feature X" WITHOUT re-archaeologizing the vendored PDF4QT core.

## The key fact

The vendored PDF4QT core (Pdf4QtLibCore) already contains the ENGINE for
nearly every interactive PDF-editor feature — upstream PDF4QT ships full GUI
apps (PdfEdit/PdfViewer) that we deliberately stripped (ADR-0001/0002: no GUI,
headless, deterministic, CLI-first). So "implement annotations" mostly means
**expose an existing engine API via albdf CLI + tests**, not write new engine
code. The genuinely missing layer is the GUI (thumbnails, click-to-select,
drag, sidebar) which is deferred by ADR-0002.

## Engine API already present (vendored, upstream-proven)

| Capability | Engine class(es) | Notes |
|---|---|---|
| Edit existing text | `PDFDocumentTextFlow` / `PDFDocumentTextFlowEditorModel` / `PDFPageContentEditorProcessor` | text-flow extraction, select-by-rect/contained-text, setData edits. **This is the R#4 file** (mixed add-text drops /ActualText) |
| Font/size/color/alignment, bold/italic/underline | `PDFEditedPageContentElementText` + content-stream builder | text-state per element |
| Find & replace | `PDFTextSearchEngine` (RTL-aware, ours) + text-flow edit | combine: search → select → replace |
| Move/resize/rotate/delete images | `PDFDocumentManipulator` (addImage, assembled pages), `PDFObjectEditorModel`, content-editor Image elements | `delete-object` CLI already exists |
| Replace/insert images | `PDFDocumentManipulator::addImage` + `PDFPageContentEditorProcessor` | |
| Opacity / compression | `PDFImageOptimizer` + `PDFImageCompressor` + `PDFObjectEditorModel` | settings structs exist |
| Crop / brightness / contrast | partial — `PDFImage` manipulation; visual ops are GUI-level | |
| Page ops (insert/delete/duplicate/reorder/rotate) | `PDFDocumentManipulator` | CLI already ships: `rotate`, `move-page`, `delete-page`, `unite`, `separate` |
| Split / merge | `unite` / `separate` CLI | tested |
| Page size/orientation/margins | `PDFPageGeometry` + page boxes | crop-box workflow is GUI |
| Zoom / scroll / thumbnails | — | **100% GUI, nothing to do in engine** |
| Highlight / comments / sticky notes | `PDFAnnotation` full API (setContents, setColor, setFlags, Highlight/FreeText/Popup types) | engine ready, **no CLI exposure** |
| Drawing: freehand/arrows/lines/rect/circle/polygon/ink | `PDFAnnotation` (Line/Square/Circle/Polygon/Ink) + content-stream path elements | engine ready, no CLI |
| Stamps ("Approved" etc.) | `PDFAnnotation::Stamp` + `setStamp` | engine ready, no CLI |
| Stroke color/width, transparency | `PDFAnnotation` setters + `PDFObjectEditorModel` | engine ready |

## CLI surface today (src/PdfTool/*.cpp)

`addtext`, `attachments`, `audiobook`, `certstore`, `colorprofiles`, `decrypt`,
`deleteobject`, `deletepage`, `diff`, `encrypt`, `fetchimages`, `fetchtext`,
`formfill`, `formlist`, `info` (+fonts/inks/javascript/metadata/nameddestinations/
pageboxes/structuretree), `inkcoverage`, `movepage`, `optimize`, `recognizetext`,
`redact`, `removeexternallinks`, `render`, `rotate`, `searchtext`, `separate`,
`sign`, `statistics`, `unite`, `verifysignatures`, `xml`.

No annotation, no image-insert, no text-edit command yet.

## Distance-to-feature tiers (as of 0.2.0)

- **Tier 1 — engine done, CLI wiring missing (~1-2 weeks):** annotations
  (highlight/comments/stamps/shapes/ink), image insert/replace/properties,
  page duplicate/insert. Natural M12.
- **Tier 2 — engine done, needs work (2-4 weeks):** text editing via CLI +
  R#4 /ActualText fix + find/replace pipeline; crop/brightness/contrast.
- **Tier 3 — GUI (the user-facing product):** thumbnails panel, zoom presets,
  smooth scrolling, click-to-select, drag-to-move, sidebar comments w/ replies.
  NOT engine work — the thin Qt shell ADR-0002 deferred. Upstream PdfEdit is
  mostly intact in the vendored base; restoring it with our RTL engine
  underneath is re-wiring, not a rewrite.
