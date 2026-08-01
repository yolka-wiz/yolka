#!/usr/bin/env bash
# build-identity.sh — regenerate this identity snapshot from a live profile.
# Usage: bash build-identity.sh [profile-name] [HERMES_HOME]
# Defaults: profile "devops", HERMES_HOME $HERMES_HOME or ~/.hermes
# Run from the identity repo checkout. Review `git diff` before committing.
set -euo pipefail

PROFILE_NAME="${1:-devops}"
HERMES_HOME="${2:-${HERMES_HOME:-$HOME/.hermes}}"
# Normalize: HERMES_HOME may point at the config root OR directly at the
# profile dir (this host sets HERMES_HOME=.../profiles/devops in-session).
if [ -f "$HERMES_HOME/SOUL.md" ] && [ "$(basename "$HERMES_HOME/..")" = "profiles" ]; then
  HERMES_HOME="$(cd "$HERMES_HOME/../.." && pwd)"
fi
SRC="$HERMES_HOME/profiles/$PROFILE_NAME"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ -d "$SRC" ] || { echo "!! profile not found: $SRC"; exit 1; }

mkdir -p "$REPO_DIR/memories" "$REPO_DIR/skills" "$REPO_DIR/cron" "$REPO_DIR/soul"

cp "$SRC/SOUL.md" "$REPO_DIR/SOUL.md"
cp "$SRC/soul/soul.json" "$REPO_DIR/soul/"
cp "$SRC/memories/MEMORY.md" "$REPO_DIR/memories/"
cp "$SRC/memories/USER.md" "$REPO_DIR/memories/"
[ -f "$SRC/.env" ] && cp "$SRC/.env" "$REPO_DIR/.env"
[ -f "$SRC/auth.json" ] && cp "$SRC/auth.json" "$REPO_DIR/auth.json"

# Skills — full tree minus cache/backup internals
tar -C "$SRC/skills" -cf - \
  --exclude='.curator_backups' --exclude='.hub' --exclude='.skills_prompt_snapshot.json' . \
  | tar -C "$REPO_DIR/skills" -xf -

# Cron scheduler state
tar -C "$SRC/cron" -cf - --exclude='*.lock' --exclude='ticker_*' . \
  | tar -C "$REPO_DIR/cron" -xf -

# Config — always sanitize the GitHub PAT before it touches git
python3 - "$SRC/config.yaml" "$REPO_DIR/config.yaml" <<'PYEOF'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
txt = open(src).read()
new = re.sub(r'(GITHUB_PERSONAL_ACCESS_TOKEN=)[^\s"\'»]+', r'\1«YOUR_GITHUB_PAT»', txt)
open(dst, 'w').write(new)
print("config.yaml sanitized (PAT -> placeholder)")
PYEOF

echo "==> snapshot refreshed. Review:"
echo "    git status && git diff --stat"
echo "    git commit -am 'sync identity snapshot' && git push"
