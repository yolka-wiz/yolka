#!/usr/bin/env bash
# upstream-contribution-audit.sh — measure a fork against its upstream for PR feasibility.
#
# Usage: bash scripts/upstream-contribution-audit.sh [REPO_DIR] [UPSTREAM_REMOTE] [FILE]
#   REPO_DIR        path to the fork checkout (default: current dir)
#   UPSTREAM_REMOTE remote name for upstream (default: upstream)
#   FILE            one upstream-named file to show the CRLF-ignored semantic delta for,
#                   default: Pdf4QtLibCore/sources/pdftextlayoutgenerator.cpp
#
# Prints: merge-base, ahead/behind counts, diff classification, the genuinely-modified file
# list (renames excluded), and a whitespace/CRLF-ignored semantic diff for the given file
# (upstream path vs the fork's src/ vendored path — albdf layout assumed).
#
# Traps handled: rename detection (git diff --name-status shows R entries for the src/
# tree move — the M list is the truth), CRLF noise in blob-to-blob diffs (-w -B), and
# --stat options order.
set -euo pipefail

REPO="${1:-$(pwd)}"
REMOTE="${2:-upstream}"
FILE="${3:-Pdf4QtLibCore/sources/pdftextlayoutgenerator.cpp}"

cd "$REPO" || { echo "no such repo dir: $REPO" >&2; exit 1; }
git fetch "$REMOTE" --tags >/dev/null 2>&1 || true

UP="$REMOTE/master"
if ! git rev-parse --verify -q "$UP" >/dev/null; then
    echo "upstream ref '$UP' not found (remote '$REMOTE'?)" >&2
    exit 1
fi

MB="$(git merge-base "$UP" HEAD)"
echo "merge-base:    $(git rev-parse --short "$MB")"
echo "fork ahead:    $(git rev-list --count "$MB"..HEAD) commits"
echo "fork behind:   $(git rev-list --count "$MB".."$UP") commits"
echo
echo "=== diff classification ($UP..HEAD) ==="
git diff --name-status "$UP"..HEAD | awk '
    $1=="A" {a++}
    $1=="M" {m++; print "  M: " $2}
    $1=="D" {d++}
    substr($1,1,1)=="R" {r++}
    {total++}
    END {printf "added=%d modified=%d deleted=%d renamed=%d total=%d\n", a, m, d, r, total}'
echo
echo "=== genuinely MODIFIED upstream files (renames excluded) ==="
git diff --name-status "$UP"..HEAD | awk '$1=="M" {print $2}'
echo
echo "=== semantic delta (CRLF/whitespace ignored): $FILE ==="
FORK="src/$FILE"
if git cat-file -e "$UP:$FILE" 2>/dev/null && git cat-file -e "HEAD:$FORK" 2>/dev/null; then
    git diff -w -B --ignore-space-at-eol --stat "$UP:$FILE" "HEAD:$FORK"
    REAL=$(git diff -w -B "$UP:$FILE" "HEAD:$FORK" | grep -E '^[+-]' \
        | grep -v -E '^(\+\+\+|---)' | grep -v -E '^\+\+\+' \
        | grep -v -E '^\s*[+-]\s*(//|/\*|\*|#)' | grep -c '^[+-]' || true)
    echo "--- real +/- lines after stripping headers/comments: ${REAL:-0} ---"
else
    echo "(path pair not found — check the fork's src/ vendored layout and the upstream path)"
fi
