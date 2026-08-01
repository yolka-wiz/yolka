---
name: persian-excel-tender
description: Process and transform Persian-language procurement/tender Excel workbooks (LOM / لیست قیمت تجهیزات) — multi-sheet consolidation, Mohaimen-style uniform formatting, RTL-aware styling, and smart item bundling.
category: productivity
---

# Persian Excel Tender / LOM Consolidation

Transform Persian-language multi-sheet LOM (List of Materials / لیست قیمت تجهیزات) Excel workbooks into consolidated, uniformly styled single-sheet output with section headers, row grouping, and optional item bundling.

## When to use

- Source has 6–8+ sheets named CIVIL-LOM, MECH-LOM, POWER-LOM, ACS-LOM, CCTV-LOM, PASSIVE-LOM, FAS-LOM, FES-LOM (or similar)
- Each sheet has columns: ردیف, تجهیزات, توضیحات, مقدار, واحد, برند
- Target should be a single sheet with section headers per discipline, 18pt uniform data, and collapsible row groups
- Persian text must render correctly (Calibri, center-aligned, wrap=ON)

## Tools needed

| Tool | Purpose |
|---|---|
| `openpyxl` | Read/write .xlsx with full style control |
| `python-bidi` + `arabic-reshaper` (optional) | For advanced RTL rendering in scripts |

Install: `pip install openpyxl`

## Structural transformation rules (Mohaimen pattern)

| # | Feature | Source | Target |
|---|---------|--------|--------|
| 1 | Sheets | Multi-sheet (one per discipline) | Single sheet per file |
| 2 | Section headers | None | `بخش ...` merged A:F, 22pt bold |
| 3 | Data cells | 12–14pt mixed | 18pt regular, center-center, wrap=ON |
| 4 | Header coloring | Green fill (FF92D050) | No fill (theme color only) |
| 5 | Template columns | A–F (6) | A–F + G–N reserved, dark blue fill FF0070C0 on row 1 |
| 6 | Row grouping | None | outline_level=1 on all data rows per section |
| 7 | Page setup | Default | Landscape A4, print area A:F |
| 8 | Borders | Mixed | Thin on all sides, every cell |

## Section name mapping

Sheet names like `CIVIL-LOM` or `MECH-LOM` are automatically mapped to Persian section headers:

| Sheet pattern | Section header |
|---|---|
| CIVIL | بخش عمران |
| MECH / MECHANICAL | بخش مکانیک |
| POWER | بخش POWER |
| ACS | بخش اکسس کنترل |
| CCTV | بخش CCTV |
| PASSIVE | بخش PASSIVE |
| FAS | بخش FAS |
| FES | بخش FES |

Customise `SECTION_NAMES` dict in the script for additional mappings.

## Bundling rules (1–2 per section, except مکانیک)

Bundle adjacent items that share context/brand/qty into one general line item.

| Section | Bundle | Replaces |
|---------|--------|----------|
| عمران | سازه‌های فلزی و ورق‌های گالوانیزه | پروفیل شاسی + ریل زیر رک + ورق کف |
| POWER | کابل‌های افشان مسی سایزهای مختلف | All CABLE x* items |
| POWER | سیستم ارت و صاعقه‌گیر | میله صاعقه‌گیر + تسمه مسی + شینه‌های ارت |
| FAS | شستی‌های تخلیه و توقف تخلیه | Both push button switches |
| FAS | مراکز اعلام حریق (معمولی + دارای اطفا) | Both fire panel types |
| FES | سیستم کامل اطفای گازی FM200 | Entire cylinder + components + piping |
| CCTV | دوربین‌های HIKVISION BULLET و DOME | Both camera types |
| PASSIVE | فیبر نوری OS2 مسیر A و B | Redundant fiber pair |
| PASSIVE | ODF خارجی A و B | Redundant ODF pair |

**Pitfall:** Don't over-bundle — at most 1–2 bundles per section. The user said "we dont want to summarize too much."

## Scripts

### `lom_consolidate.py` — basic structural consolidation
Single-sheet Mohaimen-style output with section headers, row grouping, page setup, and template columns.

```bash
python lom_consolidate.py "input.xlsx" --output "output.xlsx" \\
  --sheet-name "IT-01" \\
  --order "MECH,CIVIL,POWER,ACS,CCTV,PASSIVE,FAS,FES"
```

### `lom_bundle.py` — consolidation + smart item bundling
Adds the bundling step after consolidation. Same CLI interface.

```bash
python lom_bundle.py "file1.xlsx" "file2.xlsx" \\
  --order "MECH,CIVIL,POWER,ACS,CCTV,PASSIVE,FAS,FES"
```

Each input file produces its own output: `<stem>-Mohaimen.xlsx`.

## Tips

- **FES sheets** use a different column layout (7 cols, merged cells, brand in col G). The bundling script handles this by condensing the entire FES section into one "سیستم کامل اطفای گازی FM200" line item.
- **Empty rows** in the source (e.g. separator rows) are automatically filtered out.
- **Row ordering** defaults to source sheet order; use `--order` to specify a custom sequence.
- The generated files open correctly in both Excel and LibreOffice, but LibreOffice may render some Persian glyphs differently — Calibri has good Persian support.
