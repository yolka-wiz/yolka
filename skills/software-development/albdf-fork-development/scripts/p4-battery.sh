#!/usr/bin/env bash
# Phase-4 real-PDF validation battery for the albdf CLI.
# Usage: bash p4-battery.sh <path-to-pdf> <search-term> [--expect-no-text]
# Read-only w.r.t. the repo; writes only to a temp workdir.
# Checks: info rc, render determinism (sha256 two runs), fetch-text,
#         search-text, add-text RTL determinism + searchability, exit codes.
# SEE SKILL §12: user-uploaded test PDFs live in /home/agent/workspace/test-pdfs/
# (OUTSIDE the repo — never commit them).
set -u
BIN="/home/agent/workspace/al-bdf-engine/src/build/bin/albdf"
FONT="/home/agent/workspace/al-bdf-engine/src/tests/fonts/NotoNaskhArabic-Regular.ttf"
PDF="$1"
TERM="$2"
EXPECT_NO_TEXT="${3:-}"
WORK="$(mktemp -d /tmp/p4bat.XXXXXX)"
echo "BATTERY pdf=$PDF term=$TERM expect_no_text=$EXPECT_NO_TEXT"
echo "work=$WORK"

fail=0
note() { echo "NOTE: $*"; }
pass() { echo "PASS: $*"; }
bad()  { echo "FAIL: $*"; fail=$((fail+1)); }

# 1. info
echo "--- 1. info ---"
OUT=$(QT_QPA_PLATFORM=offscreen "$BIN" info "$PDF" 2>&1); RC=$?
echo "$OUT" | grep -E 'Page count|Title' | head -3
[ "$RC" -eq 0 ] && pass "info rc=0" || bad "info rc=$RC"

# 2. render determinism (use --image-output-dir; bare <out> drops Image_N.png next to INPUT)
echo "--- 2. render determinism ---"
mkdir -p "$WORK/r1" "$WORK/r2"
QT_QPA_PLATFORM=offscreen "$BIN" render "$PDF" --image-output-dir "$WORK/r1" --page-select 1 >/dev/null 2>&1
QT_QPA_PLATFORM=offscreen "$BIN" render "$PDF" --image-output-dir "$WORK/r2" --page-select 1 >/dev/null 2>&1
if [ -f "$WORK/r1/Image_1.png" ] && [ -f "$WORK/r2/Image_1.png" ]; then
    H1=$(sha256sum "$WORK/r1/Image_1.png" | cut -d' ' -f1)
    H2=$(sha256sum "$WORK/r2/Image_1.png" | cut -d' ' -f1)
    [ "$H1" = "$H2" ] && pass "render deterministic $H1" || bad "render non-deterministic $H1 vs $H2"
else
    bad "render produced no Image_1.png ($(ls $WORK/r1 2>/dev/null | tr '\n' ' '))"
fi

# 3. fetch-text
echo "--- 3. fetch-text ---"
TXTOUT=$(QT_QPA_PLATFORM=offscreen "$BIN" fetch-text "$PDF" 2>/dev/null)
CHARS=$(printf '%s' "$TXTOUT" | wc -c)
echo "extracted chars: $CHARS"
if [ -n "$EXPECT_NO_TEXT" ]; then
    [ "$CHARS" -le 10 ] && pass "no-text expected confirmed ($CHARS chars)" || note "no-text expected but $CHARS chars found"
else
    [ "$CHARS" -gt 10 ] && pass "text extracted ($CHARS chars)" || note "low chars ($CHARS) — see report"
fi

# 4. search-text (count line is 4-space-indented: '    2'; match rows show visual order)
echo "--- 4. search-text ---"
if [ -n "$EXPECT_NO_TEXT" ]; then
    note "search skipped (no-ToUnicode doc)"
else
    SROUT=$(QT_QPA_PLATFORM=offscreen "$BIN" search-text "$PDF" "$TERM" 2>&1)
    if echo "$SROUT" | grep -qE '^ *[0-9]+ *$'; then
        pass "search ran (count=$(echo "$SROUT" | grep -E '^ *[0-9]+ *$' | head -1 | tr -d ' '))"
    else
        note "search returned no count — inspect output"
    fi
fi

# 5. add-text RTL determinism + searchability
echo "--- 5. add-text RTL ---"
if [ -n "$EXPECT_NO_TEXT" ]; then
    note "add-text roundtrip skipped (no-ToUnicode doc — add-text still works on visuals but extraction can't verify)"
else
    QT_QPA_PLATFORM=offscreen "$BIN" add-text "$PDF" "$WORK/rtl1.pdf" --text "تست رندوم" --rtl --font "$FONT" --x 100 --y 100 --page 1 >/dev/null 2>&1
    QT_QPA_PLATFORM=offscreen "$BIN" add-text "$PDF" "$WORK/rtl2.pdf" --text "تست رندوم" --rtl --font "$FONT" --x 100 --y 100 --page 1 >/dev/null 2>&1
    if [ -f "$WORK/rtl1.pdf" ] && [ -f "$WORK/rtl2.pdf" ]; then
        H1=$(sha256sum "$WORK/rtl1.pdf" | cut -d' ' -f1); H2=$(sha256sum "$WORK/rtl2.pdf" | cut -d' ' -f1)
        [ "$H1" = "$H2" ] && pass "add-text deterministic $H1" || bad "add-text non-deterministic"
        S2=$(QT_QPA_PLATFORM=offscreen "$BIN" search-text "$WORK/rtl1.pdf" "رندوم" 2>&1 | grep -cE '^ *[0-9]+ *$')
        [ "$S2" -ge 1 ] && pass "added text searchable ($S2 matches)" || note "added text NOT searchable — inspect"
    else
        bad "add-text produced no output"
    fi
fi

# 6. exit-code contract (0 success, 4 ErrorDocumentReading, 7 ErrorInvalidArguments)
echo "--- 6. exit-code contract ---"
QT_QPA_PLATFORM=offscreen "$BIN" info /nonexistent.pdf >/dev/null 2>&1; RC=$?
[ "$RC" -ne 0 ] && pass "missing file -> rc=$RC (nonzero)" || bad "missing file rc=0"
QT_QPA_PLATFORM=offscreen "$BIN" info "$PDF" --bogus-flag >/dev/null 2>&1; RC=$?
echo "bogus flag rc=$RC"
[ "$RC" -ne 0 ] && pass "bogus flag rejected" || bad "bogus flag accepted"

echo ""
echo "BATTERY RESULT: fail=$fail work=$WORK"
exit $fail
