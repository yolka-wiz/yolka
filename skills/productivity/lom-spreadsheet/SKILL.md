---
name: 'lom-spreadsheet'
version: '1.0'
category: 'productivity'
description: >
  Process Persian LOM (List of Materials) Excel files for data center
  infrastructure projects — consolidate multi-sheet workbooks into a
  single-sheet Mohaimen-style format with unified styling, section headers,
  row grouping, and smart item bundling.
triggers:
  - 'user has an Excel LOM file (list of materials) with Persian/Farsi text'
  - 'user asks to consolidate LOM/BOQ sheets into one workbook'
  - 'user asks to bundle or simplify line items in an equipment list'
  - 'analyse an Excel file for structure, styling, or content patterns'
toolsets:
  - file
  - terminal
  - delegation
scripts:
  - 'scripts/lom_consolidate.py — single-file consolidation (plain)'
  - 'scripts/batch_lom_consolidate.py — batch multi-file consolidation'
  - 'scripts/lom_bundle.py — consolidation + smart bundling in one pass'
---

# LOM Spreadsheet Processing

Consolidate multi-sheet Persian LOM (List of Materials) Excel files into a
single-sheet Mohaimen-style format suitable for data center infrastructure
tenders.

## Workflow

### 1. Initial Analysis

When a user provides a LOM `.xlsx` file, first inspect its structure:

```bash
python -c "
import openpyxl
wb = openpyxl.load_workbook('path/to/file.xlsx')
for s in wb.sheetnames:
    ws = wb[s]
    print(f\"'{s}': {ws.max_row}r x {ws.max_column}c, dims={ws.dimensions}\")
wb.close()
"
```

Note:
- Sheet names (typically English abbreviations: CIVIL, MECH, POWER, ACS, CCTV, etc.)
- Row/column counts
- Whether each sheet has title row + header row + data rows
- Merged cells, column widths

### 2. Structural Transform (Mohaimen Style)

The consolidation script applies these rules:

| # | Rule | Detail |
|:---:|---|---|
| 1 | **Consolidate** | All sheets → 1 sheet named after source file |
| 2 | **Section headers** | `بخش ...` merged A:F, **22pt bold**, center-wrap |
| 3 | **Data cells** | **18pt regular**, center-center, wrap=ON everywhere |
| 4 | **Coloring** | **Dark blue fill FF0070C0** on G1:N1 (template columns) |
| 5 | **Row grouping** | **outline_level=1** on all data rows per section |
| 6 | **Page setup** | **Landscape A4**, print area = A:F |
| 7 | **Columns** | A–F (ردیف, تجهیزات, توضیحات, مقدار, واحد, برند) + G–N empty |
| 8 | **Borders** | **Thin** on all sides, every cell |
| 9 | **Title row** | First row merged A:F, **20pt bold** |

Run single-file consolidation:

```bash
python scripts/lom_consolidate.py "input.xlsx" \
  --sheet-name "IT-01" \
  --order "MECH,CIVIL,ACS,POWER,FAS,FES,CCTV,PASSIVE"
```

### 3. Section Ordering

Sections follow a configurable order. Default Persian names:

| Sheet Keyword | Section Header |
|:---|---:|
| MECH / MECHANICAL | بخش مکانیک |
| CIVIL | بخش عمران |
| POWER | بخش POWER |
| ACS | بخش اکسس کنترل |
| CCTV | بخش CCTV |
| PASSIVE | بخش PASSIVE |
| FAS / FIRE | بخش FAS |
| FES | بخش FES |

Use `--order "MECH,CIVIL,ACS,POWER,FAS,FES,CCTV,PASSIVE"` for the
standard data-center ordering. Sheets not in the order list are appended
at the end automatically.

### 4. Batch Processing

For multiple LOM files → one workbook (one sheet per file):

```bash
python scripts/batch_lom_consolidate.py \
  --output "path/to/LOM-ALL-Mohaimen.xlsx" \
  --order "MECH,CIVIL,ACS,POWER,FAS,FES,CCTV,PASSIVE" \
  --sheet-names "DG,NOC,IT02" \
  "LOM -DG.xlsx" "LOM-NOC.xlsx" "LOM -IT02.xlsx"
```

### 5. Combined Consolidation + Bundling

Use `scripts/lom_bundle.py` for a single-pass consolidation that
also applies smart bundling. Same styling output as `lom_consolidate.py`
but with bundled line items.

```bash
python scripts/lom_bundle.py "path/to/LOM.xlsx" --order "MECH,CIVIL,POWER,..."
```

### 6. Smart Item Bundling Rules

When the user asks to simplify/generalize line items:

**User preference (captured Jul 2026):**
- **At most 1-2 bundles per section** — do not over-summarize
- **Bundle adjacent related items**, especially same-category items of
  the same count (e.g. 14 cable types → "کابل‌های افشان مسی سایزهای مختلف")
- **Same-qty adjacent items** are the strongest bundle candidates
- **Skip the مکانیک section** unless explicitly asked
- User dislikes over-summarization: 'dont summarize too much'

**Bundle identification heuristics:**

| Heuristic | Example |
|:---|---:|
| Same brand + same unit | 14 CABLE items from same supplier |
| Same qty + adjacent | شستی تخلیه + شستی توقف (both qty=1) |
| A/B redundant pair | OS2 Path A + Path B, ODF-EXT-A/B |
| Component system (FES) | Whole FM200 system → one line |
| Structural metal (brand `-`, qty=۱) | پروفیل + ریل + ورق کف |

**FES Special Handling:**
FES-LOM sheets use a 7-column layout (brand in column G) with merged
cells B3:B11 and E3:E11 — the standard 6-column reader produces garbled
data. Always handle FES as a special case: emit a single system item
describing the complete FM200 fire suppression system rather than
attempting to read individual components.

**Brand collection:**
Bundle brands should be collected from the actual matched items'
data, never hardcoded. If matched items have different brands, join
them with a comma.

**Section-specific bundle patterns** (see `references/bundling-patterns.md`):
- POWER: cable pack + earthing system
- FAS: push buttons + control panels
- FES: complete system (one item)
- CCTV: bullet + dome cameras
- PASSIVE: OS2 A/B + ODF-EXT A/B
- عمران: structural metal items

## Pitfalls

- **Path escaping**: Use raw string `r"C:\path"` or double-backslashes in
  Python. In bash (git-bash), MSYS paths like `/c/Users/...` work.
- **Merged cells**: `MergedCell` objects have no `.column_letter` — always
  catch `AttributeError` when iterating cells in merged ranges.
- **Sheet name length**: Excel max = 31 chars. The script truncates safely.
- **Theme colors**: openpyxl serializes theme colors differently than
  explicit RGB — `cell.fill.fgColor.rgb` may return `"Values must be of
  type <class 'str'>"` for theme colors; check `cell.fill.fgColor.theme`
  instead.
- **Font size for Persian**: 18pt regular is the standard data cell size
  for Persian LOM sheets — large enough to read in print, consistent
  across all data cells.
- **Row grouping only data rows**: section headers (outline_level=0) and
  the title/header rows must NOT be grouped — only the actual data rows
  under each section get outline_level=1.

## Verification

After generating, verify the output matches the pattern:

```python
from openpyxl import load_workbook
wb = load_workbook("output.xlsx")
ws = wb.active
# Check dark blue fill on G1:N1
assert ws.cell(1, 7).fill.fgColor.rgb == 'FF0070C0'
# Check outline grouping
assert ws.row_dimensions[4].outline_level == 1  # first data row
assert ws.row_dimensions[3].outline_level == 0  # section header
# Check page setup
assert ws.page_setup.orientation == 'landscape'
assert ws.page_setup.paperSize == 9
```

## References

- `scripts/lom_consolidate.py` — single-file consolidation with full
  Mohaimen-style formatting
- `scripts/batch_lom_consolidate.py` — multi-file → one workbook batch
  processor
