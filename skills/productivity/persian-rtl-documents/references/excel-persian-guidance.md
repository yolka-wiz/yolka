# Persian Excel Processing — Lessons & Patterns

Collected from working with Persian-language LOM (لیست اقلام و مصالح)
data center procurement spreadsheets on Windows.

## Reading Persian Text from Excel

Python's `openpyxl` reads Persian (Arabic-script) text correctly without
any special encoding — Excel stores text as Unicode internally.

```python
import openpyxl
wb = openpyxl.load_workbook("file.xlsx", data_only=True)
ws = wb.active
cell_value = ws.cell(row=1, column=1).value  # Persian text — works as-is
```

## Common Pitfalls

### Path issues on Windows with git-bash
When running Python through git-bash (MSYS), `/c/Users/...` paths sometimes
fail in Python. Use `r"C:\Users\..."` (raw Windows path) instead:

```python
# ✅ Works
path = r"C:\Users\netcon\Downloads\LOM -IT01.xlsx"

# ❌ May fail from git-bash Python
path = "/c/Users/netcon/Downloads/LOM -IT01.xlsx"
```

### Merged cells
`openpyxl` represents merged cells as `MergedCell` objects with no
`column_letter` attribute. Always handle them:

```python
for cell in row:
    try:
        col = cell.column_letter
    except AttributeError:
        col = '?'  # MergedCell
```

### Persian digits
Excel may store Persian/Arabic digits (۱۲۳) vs Western digits (123) — both
are valid Unicode. Check `str(v).isdigit()` won't catch Arabic-Indic digits.

## LOM Consolidation Pattern

The `lom_consolidate.py` script (at `scripts/`) transforms multi-sheet
LOM workbooks into a single-sheet "Mohaimen" format.

### Full structural transformation

| # | Feature | Source | Target |
|:---:|---|---|---|
| 1 | **Consolidation** | N sheets | 1 sheet (named after source file) |
| 2 | **Section headers** | None | `بخش ...` merged A:F, **22pt bold**, center-wrap |
| 3 | **Data cells** | Mixed sizes | **18pt regular**, center-center, wrap=ON |
| 4 | **Row grouping** | None | **outline_level=1** on all data rows (collapsible) |
| 5 | **Template cols** | N/A | **G–N added**, dark blue fill (FF0070C0) on row 1 |
| 6 | **Borders** | Mixed | **Thin** on all sides, every cell |
| 7 | **Page setup** | Default | **Landscape A4**, print area = A:F |

### Run

```bash
python lom_consolidate.py "input.xlsx" \
  --order "MECH,CIVIL,ACS,POWER,FAS,FES,CCTV,PASSIVE" \
  --sheet-name "IT-01"
```

### Structural analysis workflow (when reverse-engineering a template)

When you need to extract the structural pattern from a reference Excel file,
check ALL of these — missing even one produces an incomplete transformation:

1. **Fonts** — size, bold, color, name per cell category (title/header/section/data)
2. **Fills** — any PatternFill with explicit RGB (not just theme colors)
3. **Alignment** — horizontal, vertical, wrap_text
4. **Borders** — style per side (thin/medium/thick/none)
5. **Merged cells** — which ranges, which rows
6. **Row grouping** — `ws.row_dimensions[r].outline_level`
7. **Column widths** — `ws.column_dimensions[letter].width`
8. **Row heights** — `ws.row_dimensions[r].height`
9. **Page setup** — orientation, paper size, print area
10. **Freeze panes / auto filter** — `ws.freeze_panes`, `ws.auto_filter.ref`

## Dependencies

```bash
pip install openpyxl pandas  # Core Excel processing
pip install arabic-reshaper python-bidi  # Persian display rendering (optional)
```
