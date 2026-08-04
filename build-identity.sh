#!/usr/bin/env bash
# build-identity.sh — refresh this identity snapshot from a live Hermes profile.
# Secrets policy: NEVER copies .env/auth.json into the repo. Only the sanitized
# config.yaml (PAT redacted), SOUL, memories (scrubbed), skills, cron state.
#
# Usage: bash build-identity.sh [profile-name] [HERMES_HOME]
# Defaults: profile "yolka", HERMES_HOME $HERMES_HOME or ~/.hermes
# Run from the identity repo checkout. Review `git diff` before committing.
set -euo pipefail

PROFILE_NAME="${1:-yolka}"
HERMES_HOME="${2:-${HERMES_HOME:-$HOME/.hermes}}"
# Normalize: HERMES_HOME may point at the config root OR directly at a profile
# dir (this host sets HERMES_HOME=.../profiles/yolka in-session).
if [ -d "$HERMES_HOME" ] && [ "$(basename "$(cd "$HERMES_HOME/.." 2>/dev/null && pwd)")" = "profiles" ]; then
  HERMES_HOME="$(cd "$HERMES_HOME/../.." && pwd)"
fi
SRC="$HERMES_HOME/profiles/$PROFILE_NAME"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ -d "$SRC" ] || { echo "!! profile not found: $SRC"; exit 1; }

mkdir -p "$REPO_DIR/memories" "$REPO_DIR/skills" "$REPO_DIR/cron" "$REPO_DIR/soul"

cp "$SRC/SOUL.md" "$REPO_DIR/SOUL.md"
[ -f "$SRC/soul/soul.json" ] && cp "$SRC/soul/soul.json" "$REPO_DIR/soul/"

# Memories — STRIP known secret patterns before they touch git
python3 - "$SRC/memories/MEMORY.md" "$REPO_DIR/memories/MEMORY.md" <<'PYEOF'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
txt = open(src, encoding='utf-8', errors='replace').read()
# redact common credential shapes: tokens, keys, passwords, IP:port creds
txt = re.sub(r'(?i)(token|key|secret|password|pass)\s*[=:]\s*\S+', r'\1=<REDACTED>', txt)
txt = re.sub(r'\b(ghp_|sk-|s\.)[A-Za-z0-9_-]{10,}\b', '<REDACTED>', txt)
txt = re.sub(r'(?i)\b(user|pass|pwd)\b[=:]\s*\S+', r'\1=<REDACTED>', txt)
open(dst, 'w', encoding='utf-8').write(txt)
print("MEMORY.md scrubbed")
PYEOF
cp "$SRC/memories/USER.md" "$REPO_DIR/memories/"

# Skills — full tree minus cache/backup internals
tar -C "$SRC/skills" -cf - \
  --exclude='.curator_backups' --exclude='.hub' --exclude='.skills_prompt_snapshot.json' \
  --exclude='.bundled_manifest' --exclude='.curator_state' --exclude='.usage.json' . \
  | tar -C "$REPO_DIR/skills" -xf -

# Cron scheduler state (executions only — no locks/ticks)
tar -C "$SRC/cron" -cf - --exclude='*.lock' --exclude='ticker_*' . \
  | tar -C "$REPO_DIR/cron" -xf - 2>/dev/null || true

# Config — always sanitize the GitHub PAT before it touches git
python3 - "$SRC/config.yaml" "$REPO_DIR/config.yaml" <<'PYEOF'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
txt = open(src, encoding='utf-8', errors='replace').read()
new = re.sub(r'(GITHUB_PERSONAL_ACCESS_TOKEN=)[^\s"\'»]+', r'\1«YOUR_GITHUB_PAT»', txt)
open(dst, 'w', encoding='utf-8').write(new)
print("config.yaml sanitized (PAT -> placeholder)")
PYEOF

echo
echo "==> snapshot refreshed (secrets excluded). Review:"
echo "    git status && git diff --stat"
echo "    git commit -am 'sync identity snapshot' && git push"
