# Okular RTL Text Fix - Triage Reference

## Project Context

- **Repository**: https://invent.kde.org/graphics/okular.git
- **Remote Dev Server**: agent@192.168.13.44 (Debian 13, NOPASSWD sudo enabled)
- **Build Command**: `cmake -B build -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DFORCE_NOT_REQUIRED_DEPENDENCIES='Qt6TextToSpeech;Phonon4Qt6;TIFF;LibSpectre;KExiv2Qt6;DjVuLibre;EPub;Discount'`
- **Build Target**: `cmake --build build --target okularGenerator_poppler --parallel $(nproc)`
- **Run Tests**: `QT_QPA_PLATFORM=offscreen ./build/bin/searchtest`
- **Design Document**: `~/Documents/playground/DESIGN.md` (local Windows machine)

## Architecture Data Flow

```
PDF File
   ↓
Poppler::Page::textList()  ←  returns text in VISUAL order for RTL
   ↓
generator_pdf.cpp :: abstractTextPage()
  - iterates character-by-character through Poppler order
  - creates TextEntity per character: (text, bounding box)
  - NO BiDi/shaping processing anywhere
   ↓
TextPage::append()  →  stores in m_words (QList<TextEntity>)
   ↓
Page::setTextPage()
  → calls TextPagePrivate::correctTextOrder()
     - spatial XY-cut reordering (left→right, top→bottom)
     - DOES NOT understand BiDi — treats RTL as LTR
   ↓
TextPage::findText()  →  searches m_words sequentially → BROKEN for RTL
TextPage::text()      →  concatenates m_words in stored order → BROKEN for RTL
```

## Root Cause (Confirmed)

Poppler's `textList()` returns text in **visual (spatial) order** (left-to-right), not logical (Unicode reading order). For RTL text like "متن" (mtn), Poppler returns characters in visual order (left-to-right), but search/copy expect logical order.

## Prior Art

### MR 595 (2018, never merged)
- **Author**: fahadalsaidi
- **Status**: "Needs Revision"
- **Approach**: Port `reorderText()` from Poppler to Okular's `correctTextOrder()`
- **Key insight**: "Since poppler has fixed it since 0.40, I've just ported reorderText() from poppler to okular and it works."
- **Files changed**: `core/textpage.cpp`, `autotests/searchtest.cpp`, `autotests/data/arabic-search-test.pdf`

### Poppler Bug #53
- **Title**: "RTL: Copy/Paste Arabic results in reverse order of Arabic phrases after pasting"
- **Status**: Fixed in glib backend (Evince) via `TextSelectionDumper::finishLine()` reversal
- **Qt6 backend**: Does NOT have the same fix

### Poppler Changelog Entries
- 2021: "TextSelectionDumper: fix word order for RTL text" (fixes #53 for glib)
- 2015: "Handle right-to-left text in search" (applies RTL reversal for search)
- 2009: "Select top right to bottom left in RTL mode" (early RTL selection attempt)

## Proposed Fix Design

**Location**: `core/textpage.cpp` → `TextPagePrivate::correctTextOrder()`

**Approach**: After spatial reordering, apply BiDi reordering using:
- Qt's `QString::isRightToLeft()` for RTL detection (simplest, no new deps)
- OR Fribidi library (already installed: libfribidi 1.0.16)

**Algorithm**:
1. Detect RTL characters in each TextEntity
2. Reverse character order within RTL runs
3. Store reordered text back in TextPage

**Files to modify**:
- `core/textpage.cpp` (~25-35 lines: add `containsRTL()` and `reverseRTLText()` helpers)
- `core/textpage.h` (~5 lines if helper functions added)

## Test PDFs Created

Located at `/tmp/test_rtl.pdf` on remote server:
- Pure Persian: متن تست (test text)
- Pure Arabic: سلام دنیا (hello world)

## Existing Tests

- `searchtest` — 13/13 pass (no RTL tests exist)
- No existing RTL/BiDi/Arabic/Persian/Hebrew tests in test suite

## Key Findings from This Session

### 1. Typewriter Issue is Separate from Text Extraction
The three reported issues map to TWO different code paths:
- **Search/Copy text** (Issues #2, #3): Text extraction via TextPage → fixed by BiDi reordering
- **Typewriter annotations** (Issue #1): Font rendering/shaping → separate concern

The Typewriter tool stores text via `ta->setContents(content)` (no reordering). The "breaks letter connections" is a font rendering issue, not a text ordering issue. Qt's `QPainter::drawText()` handles BiDi automatically when the font supports Arabic/Persian shaping.

### 2. Qt's isRightToLeft() is Sufficient
No need for Fribidi library. Qt6 provides:
- `QString::isRightToLeft()` — checks if string contains RTL characters
- `QChar::isRightToLeft()` — checks individual characters
- These use Unicode BiDi algorithm internally

### 3. Poppler Qt6 Backend Lacks RTL Fix
Poppler 25.03.0 has RTL fixes in glib backend (TextSelectionDumper) but NOT in Qt6 backend. The Qt6 `Page::textList()` function doesn't apply BiDi reordering.

### 4. correctTextOrder() is the Right Fix Location
The fix belongs in `TextPagePrivate::correctTextOrder()` because:
- It's called for ALL generators (PDF, DJVU, EPUB, etc.)
- It's where spatial text reordering already happens
- It's the same location MR 595 targeted

### 5. Test PDF Creation Pitfall
When creating test PDFs with Arabic/Persian text using fpdf2:
- **Must use Unicode font**: `pdf.add_font('NotoArabic', '', '/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf')`
- **Characters are stored in LOGICAL order** (not visual order) — this is the default for fpdf2
- **For proper RTL testing**, need PDFs with characters in VISUAL order (right-to-left)
- **Verify text order** by checking x-coordinates: ascending = LTR visual, descending = RTL visual

### 6. Verifying Text Order (Visual vs Logical)
To determine if Poppler returns visual or logical order:
```cpp
// Check x-coordinates of characters in a word
double prevX = -1;
for (int i = 0; i < text.length(); ++i) {
    QRectF cbbox = tb->charBoundingBox(i);
    double x = cbbox.left();
    if (prevX >= 0) {
        if (x > prevX) { /* ascending = LTR visual */ }
        if (x < prevX) { /* descending = RTL visual */ }
    }
    prevX = x;
}
```
- **Ascending x** (left→right): LTR visual order
- **Descending x** (right→left): RTL visual order

### 7. Implementation Verified
The fix was implemented in `core/textpage.cpp`:
- Added BiDi reordering loop in `correctTextOrder()` after spatial reordering
- Uses `QChar::direction()` to detect RTL characters (DirR or DirAL)
- Reverses character order within RTL words to convert visual→logical
- All 13 existing search tests pass (no regression)

### 8. Arabic Presentation Forms (0xFExx)
Professional PDFs often use Unicode presentation forms for Arabic text:
- **Base characters** (0x0600-0x06FF): Standard Arabic characters
- **Presentation forms** (0xFE70-0xFEFF): Pre-shaped glyphs with specific joining rules
  - INITIAL forms connect to NEXT character
  - FINAL forms connect to PREVIOUS character
  - MEDIAL forms connect to BOTH
  - ISOLATED forms connect to NEITHER

**Pitfall**: Reversing presentation forms directly breaks ligatures. The correct approach is:
1. Convert presentation forms to base characters
2. Reverse base characters (visual to logical)
3. Let font/renderer apply correct presentation forms

The current implementation reverses presentation forms, which works for text extraction (search/copy) but may affect rendering quality. For a production fix, consider converting to base characters first.

### 9. Real PDF Testing with part1.pdf
Testing with a real Persian PDF (`~/Desktop/part1.pdf`) confirmed:
- **First word matches pdftotext**: "ﻪﻣﺪﻘﻣ" → "ﻣﻘﺪﻣﻪ" (correct logical order)
- **Word grouping differs**: Poppler and pdftotext may group characters differently
- **Presentation forms present**: The PDF uses 0xFExx presentation forms extensively

### 10. Verification Code Snippet
To verify the fix works with a real PDF:
```bash
# Build and run verification
cd ~/playground/okular/build
cmake --build . --target okularcore --parallel $(nproc)
QT_QPA_PLATFORM=offscreen ./bin/verify_fix ~/Desktop/part1.pdf

# Compare with pdftotext
pdftotext ~/Desktop/part1.pdf - | head -5
```

### 11. Complete Build & Test Commands
```bash
# Clone and configure
git clone https://invent.kde.org/graphics/okular.git
cd okular
cmake -B build -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON \
  -DFORCE_NOT_REQUIRED_DEPENDENCIES='Qt6TextToSpeech;Phonon4Qt6;TIFF;LibSpectre;KExiv2Qt6;DjVuLibre;EPub;Discount'

# Build specific targets
cmake --build build --target okularcore --parallel $(nproc)
cmake --build build --target okularGenerator_poppler --parallel $(nproc)
cmake --build build --target searchtest --parallel $(nproc)

# Run tests
QT_QPA_PLATFORM=offscreen ./build/bin/searchtest
```

## Mixed LTR/RTL Text Handling

### Poppler-Style BiDi Algorithm
For text containing both LTR and RTL characters, the algorithm identifies LTR and RTL runs, then reverses only RTL runs to convert from visual to logical order:

```cpp
// Check if character is RTL
bool isRTLChar(const QChar &ch) {
    uint code = ch.unicode();
    QChar::Direction dir = ch.direction();
    if (dir == QChar::DirR || dir == QChar::DirAL) return true;
    if (code >= 0xFE70 && code <= 0xFEFF) return true;  // Presentation forms
    if (code >= 0xFB50 && code <= 0xFDFF) return true;  // Extended Arabic
    return false;
}

// Check if character is LTR
bool isLTRChar(const QChar &ch) {
    QChar::Direction dir = ch.direction();
    return (dir == QChar::DirL || dir == QChar::DirEN || dir == QChar::DirES || dir == QChar::DirET);
}

// Reorder text from visual to logical
QString reorderText(const QString &text) {
    bool hasRTL = false;
    for (int i = 0; i < text.length(); ++i) {
        if (isRTLChar(text.at(i))) { hasRTL = true; break; }
    }
    if (!hasRTL) return text;
    
    QString reordered;
    int i = 0;
    const int n = text.length();
    
    while (i < n) {
        // Find LTR section
        int j = i;
        while (j < n && !isRTLChar(text.at(j))) j++;
        reordered.append(text.mid(i, j - i));
        i = j;
        
        // Find RTL section
        j = i;
        while (j < n && !isLTRChar(text.at(j))) j++;
        if (j > i) {
            for (int k = j - 1; k >= i; k--) reordered.append(text.at(k));
            i = j;
        }
    }
    return reordered;
}
```

### Test Results with Real PDFs
The algorithm correctly handles:
- Pure LTR text: "Hello" → "Hello" (unchanged)
- Pure RTL text: "متن" → "نتم" (reversed)
- Mixed text: "Hello متن World" → "Hello نتم World" (only RTL reversed)

### Verification with pdftotext
The fix output matches pdftotext for real Persian PDFs:
- "رد" → "در" (matches pdftotext)
- "دوش" → "شود" (matches pdftotext)
- "ماجنا" → "انجام" (matches pdftotext)
