#!/usr/bin/env bash
# restore.sh — reincarnate yolka on a fresh Hermes install.
# Usage: bash restore.sh [profile-name] [HERMES_HOME]
# Defaults: profile "devops", HERMES_HOME $HERMES_HOME or ~/.hermes
set -euo pipefail

PROFILE_NAME="${1:-devops}"
HERMES_HOME="${2:-${HERMES_HOME:-$HOME/.hermes}}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="$HERMES_HOME/profiles/$PROFILE_NAME"

echo "==> yolka restore: profile=$PROFILE_NAME  home=$HERMES_HOME"

if ! command -v hermes >/dev/null 2>&1; then
  echo "!! hermes binary not found in PATH. Install first:"
  echo "   curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
  exit 1
fi

# 1. Profile skeleton
if [ ! -d "$PROFILE_DIR" ]; then
  echo "==> Creating profile '$PROFILE_NAME'"
  hermes profile create "$PROFILE_NAME" --description "yolka — network & server automation engineer (restored identity)" --no-alias
fi
mkdir -p "$PROFILE_DIR/memories" "$PROFILE_DIR/skills" "$PROFILE_DIR/cron" "$PROFILE_DIR/soul"

# 2. Core identity files
cp "$REPO_DIR/SOUL.md" "$PROFILE_DIR/SOUL.md"
cp "$REPO_DIR/soul/soul.json" "$PROFILE_DIR/soul/"
cp "$REPO_DIR/config.yaml" "$PROFILE_DIR/config.yaml"
[ -f "$REPO_DIR/.env" ] && cp "$REPO_DIR/.env" "$PROFILE_DIR/.env"
[ -f "$REPO_DIR/auth.json" ] && cp "$REPO_DIR/auth.json" "$PROFILE_DIR/auth.json"

# 3. Memory, skills, cron
cp -r "$REPO_DIR/memories/." "$PROFILE_DIR/memories/"
cp -r "$REPO_DIR/skills/." "$PROFILE_DIR/skills/"
cp -r "$REPO_DIR/cron/." "$PROFILE_DIR/cron/"

# 4. Placeholder guard
if grep -q 'YOUR_GITHUB_PAT' "$PROFILE_DIR/config.yaml"; then
  echo "!! WARNING: config.yaml still has the «YOUR_GITHUB_PAT» placeholder."
  echo "   Regenerate a PAT at https://github.com/settings/tokens and set it:"
  echo "   hermes config set mcp_servers.github ... (or edit the args line in config.yaml)"
fi

echo "==> Restore complete. Verification checklist:"
echo "    1. hermes profile list"
echo "    2. hermes -p $PROFILE_NAME chat -q \"Who are you?\"   # expect: My name is yolka"
echo "    3. hermes doctor"
echo "    4. hermes -p $PROFILE_NAME chat -q \"Summarize my memory and list my skills\""
