# Real-PDF test corpus (user-uploaded) — baseline probes 2026-08-08

User uploads real-world PDFs for acceptance testing. **Rule: keep them OUTSIDE the
repo** at `/home/agent/workspace/test-pdfs/` — the user explicitly said "don't keep
them in repo or include the folder in gitignore"; staging outside the repo satisfies
both readings with zero gitignore churn and zero risk of accidental commit. Never
`git add` these, never copy them into `src/tests/fixtures/`.

## The corpus (uploaded 2026-08-08, all open cleanly rc=0)

| File | Origin | Page count | Extraction profile |
|---|---|---|---|
| `b_fonts_showcase.pdf` | Chrome/Skia PDF m151 (headless) | 7 | Persian text extracts in VISUAL order; RTL search works |
| `asnad-9_39.pdf` | Microsoft Word LTSC | 1 | Partial (numbers + some text) |
| `فاکتور_فروش___الماس_شبکه_تک.pdf` | Acrobat Distiller 26.0 (PScript5) | 1 | **EMPTY** — no extraction map at all |

## Finding: Distiller Persian PDFs may have NO ToUnicode → empty fetch-text

The Persian invoice (`فاکتور_فروش___الماس_شبکه_تک.pdf`) is a **real-world case where
`albdf fetch-text` returns nothing (3 bytes, rc=0)** and the cause is upstream-engine
limitation, not a bug: byte scan shows **0 ToUnicode, 0 Type0, 0 FontFile2, 0
FontDescriptor** — text is raw glyphs in flate streams, no extraction map. Probe:

```python
data = open(pdf, 'rb').read()
print('ToUnicode:', data.count(b'ToUnicode'), 'Type0:', data.count(b'/Type0'),
      'FontFile2:', data.count(b'FontFile2'))
```

When a real PDF extracts empty: check these counts BEFORE blaming the RTL pipeline —
a Distiller PDF with zero ToUnicode/Type0 is not extractable by ANY engine. Also
note `info` prints the invoice Title as `?????` (raw bytes not UTF-8-decodable in
the console path) — cosmetic, not the extraction issue.

## Finding: Chrome/Skia showcase is the good RTL search corpus

`b_fonts_showcase.pdf` (headless Chrome, Persian text): `fetch-text` returns
visual-order Persian (`یﺎﻫ ﺖﻧﻮﻓ` = فونتهای reversed — expected, documented), and
`albdf search-text <doc> "فونت"` returns **2 real matches** with bounding boxes.
This is a great end-to-end RTL search regression doc (real producer, not our own
add-text fixture). Baseline commands:

```bash
QT_QPA_PLATFORM=offscreen albdf info  /home/agent/workspace/test-pdfs/<f>.pdf
QT_QPA_PLATFORM=offscreen albdf fetch-text /home/agent/workspace/test-pdfs/<f>.pdf
QT_QPA_PLATFORM=offscreen albdf search-text /home/agent/workspace/test-pdfs/b_fonts_showcase.pdf "فونت"
```

## Subagent transcript note (not a repo rule)

When a child ran `ctest --test-dir src/build -R rtlfree` it got
`No tests were found!!!` even though the test `UnitTestsRtlFreeText` WAS registered
in `CTestTestfile.cmake` — **`ctest -R` is CASE-SENSITIVE**; `rtlfree` does not
match `RtlFreeText`. Use the exact registered name (`-R UnitTestsRtlFreeText`) or
`-R RtlFree` — not a lowercased guess. (Child recovered by grepping
`UnitTests/CTestTestfile.cmake` for `add_test`.)
