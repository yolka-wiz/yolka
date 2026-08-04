---
name: persian-rtl-documents
description: "PDF, OCR, and Persian/Arabic/RTL text processing — Tesseract setup, Arabic reshaping, bidi handling, and PDF creation with right-to-left scripts."
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [PDF, OCR, Persian, Arabic, RTL, Tesseract, bidi, Documents]
    related_skills: [ocr-and-documents]
---

# Persian / RTL Document Processing

For general PDF extraction (text-based, English-only), see `ocr-and-documents`.
This skill covers **Arabic-script languages** (Persian, Arabic, Hebrew, Urdu) — OCR, rendering, and PDF creation with RTL text.

## Prerequisites

```bash
pip install pymupdf pytesseract Pillow opencv-python python-bidi arabic-reshaper reportlab
```

## System Setup by Platform

### Linux (Debian / Ubuntu)

```bash
# 1. Generate Persian locale (fa_IR.UTF-8)
sudo sed -i 's/^# fa_IR.UTF-8/fa_IR.UTF-8 UTF-8/' /etc/locale.gen
sudo locale-gen

# 2. Install Persian fonts
sudo apt install -y fonts-farsiweb fonts-noto-arabic

# 3. Install Tesseract with Persian support
sudo apt install -y tesseract-ocr tesseract-ocr-fas

# 4. Verify
locale -a | grep fa_IR
fc-list :lang=fa | head -5
```

**⚠️ Pitfall — locale.gen format**: The line must read `fa_IR.UTF-8 UTF-8` (two space-separated columns). A trailing space after the uncommented line causes `locale-gen` to fail with `Bad entry 'fa_IR.UTF-8 '`. If you see that error, check `/etc/locale.gen` and strip trailing whitespace.

### macOS

```bash
brew install tesseract tesseract-lang
```

### Windows

Tesseract installs to `C:\Program Files\Tesseract-OCR\` (download from [UB-Mannheim releases](https://github.com/UB-Mannheim/tesseract/releases)). Writing trained data to `Program Files` requires admin rights.

**Workaround** — store tessdata in a local directory:

```python
import pytesseract, os
TESSDATA_DIR = r"C:\path\to\local\tessdata"
os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# Always pass --tessdata-dir in config:
result = pytesseract.image_to_string(img, lang='fas+eng',
    config=f'--tessdata-dir {TESSDATA_DIR}')
```

Download trained data to your local tessdata dir:
```bash
# Best quality (LSTM+legacy, ~3MB/language)
curl -L -o tessdata/fas.traineddata \
  "https://github.com/tesseract-ocr/tessdata_best/raw/main/fas.traineddata"
# Fast (smaller ~400KB, lower accuracy)
curl -L -o tessdata/fas.traineddata \
  "https://github.com/tesseract-ocr/tessdata_fast/raw/main/fas.traineddata"
```

Also copy `osd.traineddata` from the Tesseract install dir (needed for orientation detection).

## PDF Creation with Persian Text

| PSM | Use case | Persian quality |
|-----|----------|----------------|
| 3 | Fully automatic (default) | Poor — often returns empty |
| 6 | Single uniform block | Moderate |
| **7** | **Single text line** | **Best for single lines** |
| 8 | Single word | Good for isolated words |
| **13** | **Raw line, no engine** | **Good for simple text** |

**Always use `--psm 7` or `--psm 13` for Persian/Arabic OCR.** Default PSM 3 frequently returns empty results.

## Arabic Reshaping & Bidi (Critical Pitfalls)

### For OCR-compatible rendering — reshape ONLY

```python
import arabic_reshaper
# ✅ Reshapes connected forms, preserves logical order
reshaped = arabic_reshaper.reshape("سلام دنیا")
draw.text((x, y), reshaped, font=font, fill='black')
```

### For human-visible display — reshape + get_display

```python
from bidi.algorithm import get_display
import arabic_reshaper

reshaped = arabic_reshaper.reshape(persian_text)
display_text = get_display(reshaped)  # Reorders for LTR display
draw.text((x, y), display_text, ...)  # Looks correct to humans
```

**⚠️ PITFALL**: `get_display()` reverses character order for RTL display. Text looks correct visually but Tesseract reads characters backwards, producing garbage OCR. **Never use `get_display()` before feeding text to OCR.**

## PDF Creation with Persian Text

PyMuPDF built-in fonts (`helv`, `cour`, etc.) do NOT support Arabic characters — they render as dots. Use a Unicode TTF font:

```python
import fitz
doc = fitz.open()
page = doc.new_page()
rect = fitz.Rect(50, 50, 545, 792)
page.insert_textbox(
    rect, "متن فارسی",
    fontsize=16,
    fontfile="C:/Windows/Fonts/tahoma.ttf",  # Must be Unicode font
    fontname="tahoma",
    align=fitz.TEXT_ALIGN_RIGHT,  # RTL alignment
    color=(0, 0, 0)
)
doc.save("persian.pdf")
```

**Windows fonts with Persian glyphs**: `tahoma.ttf`, `arial.ttf`, `trado.ttf`.

### Linux — System Noto Fonts + Reshaper

Linux systems have Noto Arabic fonts pre-installed or available via `fonts-noto-arabic`. Use `arabic-reshaper` + `bidi` + pymupdf to render Persian correctly:

```python
import fitz
import arabic_reshaper
from bidi.algorithm import get_display

doc = fitz.open()
page = doc.new_page()

# Find the font path
# Common locations:
#   /usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf
#   /usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf
#   /usr/share/fonts/truetype/farsiweb/  (fonts-farsiweb package)

font_path = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"

# Arabic text needs reshaping + bidi reordering for correct display
text = "سلام دنیا"
reshaped = arabic_reshaper.reshape(text)
display_text = get_display(reshaped)

page.insert_text(
    (50, 50), display_text,
    fontsize=14,
    fontfile=font_path,
    color=(0, 0, 0)
)

doc.save("persian-linux.pdf")
```

**Available Noto Arabic font paths on Debian/Ubuntu:**

| Font | Path |
|------|------|
| Noto Naskh Arabic | `/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf` |
| Noto Naskh Arabic Bold | `/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf` |
| Noto Sans Arabic | `/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf` |
| Noto Sans Arabic Bold | `/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf` |
| Noto Kufi Arabic | `/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf` |
| Farsiweb (Titr) | `/usr/share/fonts/truetype/farsiweb/Far_Titr.ttf` |

**⚠️ Pitfall — fontname parameter ignored with fontfile**: When you pass `fontfile=`, pymupdf ignores the `fontname` parameter. The font is loaded from the file path. You can pass any string as `fontname` for internal reference; it won't affect rendering.

## Image Preprocessing for Arabic OCR

```python
import cv2
import numpy as np

gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
_, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
padded = cv2.copyMakeBorder(binary, 20, 20, 20, 20,
                             cv2.BORDER_CONSTANT, value=255)
```

## Full Pipeline Example

```python
import os, fitz, pytesseract, cv2, numpy as np
from PIL import Image
import arabic_reshaper

TESSDATA_DIR = r"./tessdata"
os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def ocr_pdf_persian(pdf_path, page_num=0, dpi=200):
    """OCR a PDF page with Persian language support."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()

    # Preprocess
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    padded = cv2.copyMakeBorder(binary, 20, 20, 20, 20,
                                 cv2.BORDER_CONSTANT, value=255)

    # OCR with PSM 7 for single-line, or PSM 6 for blocks
    result = pytesseract.image_to_string(
        Image.fromarray(padded),
        lang='fas+eng',
        config=f'--tessdata-dir {TESSDATA_DIR} --psm 7'
    )
    return result.strip()
```

## Excel & Spreadsheet Processing

This skill also covers Persian/Arabic content in Excel spreadsheets — common in Iranian procurement (LOM/لیست اقلام و مصالح) and data center BoQ documents.

### Key Script

- `scripts/lom_consolidate.py` — transforms multi-sheet LOM workbooks into a single-sheet "Mohaimen" format with Persian section headers, uniform 18pt styling, row grouping, dark blue template-column fills, and landscape A4 page setup.

### Structural checklist (critical)

When reverse-engineering an Excel template, check ALL 10 dimensions:
fonts, fills, alignment, borders, merged cells, row grouping (outline_level),
column widths, row heights, page setup, freeze panes.
Missing even one produces an incomplete transformation.
See `references/excel-persian-guidance.md` for the full checklist.

See `references/excel-persian-guidance.md` for detailed guidance.

### Reading Persian from Excel (openpyxl)

```python
import openpyxl
wb = openpyxl.load_workbook("file.xlsx", data_only=True)
ws = wb.active
# Persian text reads as-is (Unicode) — no encoding tricks needed
```

### Pitfalls

- **MergedCell objects** — caught via `AttributeError` on `.column_letter`
- **git-bash paths** — use raw `r"C:\Users\..."` instead of `/c/Users/...`
- **Persian/Arabic-Indic digits** (۱۲۳) are not caught by `.isdigit()`

## Limitations

- **Tesseract Persian OCR** is limited for digitally-rendered text (synthetic fonts). It performs much better on **real scanned documents** (photographs, scans).
- For high-quality Persian OCR, consider **marker-pdf** (heavyweight, uses ML models) as documented in the `ocr-and-documents` skill.
- The `tessdata_best` models (~3MB) provide better accuracy than `tessdata_fast` (~400KB) but both are limited compared to marker-pdf.
- Excel Persian text rendering in print preview may need `arabic-reshaper` + `python-bidi` for correct display order.
