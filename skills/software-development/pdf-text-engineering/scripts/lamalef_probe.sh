#!/usr/bin/env bash
# lamalef_probe.sh — probe a PDF for the lam-alef search trap (albdf engine).
# Usage: lamalef_probe.sh <pdf> [search-term]
#
# Why: a 0-match search-text result for "سلام"/"الله" on a real PDF is only
# meaningful if the term actually exists in the document. Chrome/Skia PDFs
# extract in visual order WITH presentation forms, so the term may appear as
# logical, reversed-visual, or a U+FBEA-style ligature — or not at all.
#
# Behavior:
#   1. fetch-text the PDF, scan for lam-alef in EVERY spelling (logical لا/لأ/لإ,
#      reversed-visual ال, ligatures U+FBEA/U+FBEB) plus the lam glyph inventory.
#   2. Run search-text "$TERM" on the source PDF.
#   3. If the doc has NO lam-alef at all, synthesize the path: add-text "$TERM"
#      --rtl on a /tmp copy, then fetch-text (expect VISUAL order, e.g. مالس)
#      and search-text (expect >=1 match, matched text = visual spelling).
#      This verifies the S#3 visual-order fix (commit 4cabbf7a) end-to-end.
#
# Exit: 0 = doc contains lam-alef (search result is meaningful);
#       2 = doc had no lam-alef, synthesized round-trip ran (inspect output).
set -u
BIN="${ALBDF_BIN:-/home/agent/workspace/al-bdf-engine/src/build/bin/albdf}"
FONT="${ALBDF_FONT:-/home/agent/workspace/al-bdf-engine/src/tests/fonts/NotoNaskhArabic-Regular.ttf}"
PDF="$1"
TERM="${2:-سلام}"
TMP="$(mktemp -d /tmp/lamalef.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

QT_QPA_PLATFORM=offscreen "$BIN" fetch-text "$PDF" > "$TMP/fetched.txt" 2>/dev/null
python3 - "$TMP/fetched.txt" "$TERM" <<'PYEOF'
import sys, unicodedata
text = open(sys.argv[1], encoding='utf-8').read()
term = sys.argv[2]
forms = {'logical لا': '\u0644\u0627', 'logical لأ': '\u0644\u0623', 'logical لإ': '\u0644\u0625',
         'visual reversed ال': '\u0627\u0644', 'ligature U+FBEA': '\uFBEA', 'ligature U+FBEB': '\uFBEB'}
present = [f"{k} x{v}" for k, v in forms.items() if text.count(v)]
lam = sum(1 for c in set(text) if unicodedata.name(c, '').startswith('ARABIC LETTER LAM'))
print(f"term '{term}' (logical spelling): {text.count(term)} occurrence(s)")
print(f"lam-alef spellings present: {present or 'NONE'}")
print(f"distinct lam glyphs in doc: {lam}")
sys.exit(0 if (present or lam) else 2)
PYEOF
HAS_LAM=$?

echo "--- search-text '$TERM' on source pdf ---"
QT_QPA_PLATFORM=offscreen "$BIN" search-text "$PDF" "$TERM" 2>&1

if [ "$HAS_LAM" -ne 0 ]; then
    echo "--- doc has NO lam-alef in any spelling; add-text round-trip probe ---"
    QT_QPA_PLATFORM=offscreen "$BIN" add-text "$PDF" "$TMP/lam.pdf" \
        --text "$TERM" --rtl --font "$FONT" --x 100 --y 100 --page 1 >/dev/null 2>&1
    echo "fetch-text last line (expect VISUAL order, e.g. مالس):"
    QT_QPA_PLATFORM=offscreen "$BIN" fetch-text "$TMP/lam.pdf" 2>/dev/null | tail -1
    echo "--- search-text '$TERM' on add-text output (expect >=1 match, matched text = visual spelling) ---"
    QT_QPA_PLATFORM=offscreen "$BIN" search-text "$TMP/lam.pdf" "$TERM" 2>&1
    exit 2
fi
exit 0
