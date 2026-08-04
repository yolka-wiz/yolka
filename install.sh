#!/usr/bin/env bash
# yolka — install this identity into a Hermes profile on this machine.
# The user-friendly entry point (README.md §Install). For the machine-executable
# recipe used by external agents, see AGENT.md.
#
# Usage:
#   bash install.sh [profile-name] [HERMES_HOME]
# Defaults: profile "yolka", HERMES_HOME $HERMES_HOME or ~/.hermes
set -euo pipefail

PROFILE_NAME="${1:-yolka}"
HERMES_HOME="${2:-${HERMES_HOME:-$HOME/.hermes}}"

# Normalize: HERMES_HOME may point at the config root OR directly at a profile
# dir (this host sets HERMES_HOME=.../profiles/yolka in-session).
if [ -d "$HERMES_HOME" ] && [ "$(basename "$(cd "$HERMES_HOME/.." 2>/dev/null && pwd)")" = "profiles" ]; then
  HERMES_HOME="$(cd "$HERMES_HOME/../.." && pwd)"
fi
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="$HERMES_HOME/profiles/$PROFILE_NAME"

echo "==> yolka install: profile=$PROFILE_NAME  home=$HERMES_HOME"

if ! command -v hermes >/dev/null 2>&1; then
  echo "!! hermes binary not found in PATH. Install first:"
  echo "   curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
  exit 1
fi

# 1. Profile skeleton (lean — no bundled skills; the repo's skills/ is the set)
if [ ! -d "$PROFILE_DIR" ]; then
  echo "==> Creating profile '$PROFILE_NAME' (lean: --no-skills)"
  hermes profile create "$PROFILE_NAME" \
    --description "yolka — hybrid DevOps/network/software engineer (tech lead)" \
    --no-alias --no-skills 2>/dev/null \
    || hermes profile create "$PROFILE_NAME" --description "yolka tech lead" --no-alias
fi
mkdir -p "$PROFILE_DIR/memories" "$PROFILE_DIR/skills" "$PROFILE_DIR/cron" "$PROFILE_DIR/soul"

# 2. Core identity
cp "$REPO_DIR/SOUL.md" "$PROFILE_DIR/SOUL.md"
[ -f "$REPO_DIR/soul/soul.json" ] && cp "$REPO_DIR/soul/soul.json" "$PROFILE_DIR/soul/"
[ -f "$REPO_DIR/config.yaml" ] && cp "$REPO_DIR/config.yaml" "$PROFILE_DIR/config.yaml"
[ -f "$REPO_DIR/memories/MEMORY.md" ] && cp "$REPO_DIR/memories/MEMORY.md" "$PROFILE_DIR/memories/"
[ -f "$REPO_DIR/memories/USER.md" ] && cp "$REPO_DIR/memories/USER.md" "$PROFILE_DIR/memories/"

# 3. Secrets template — never overwrite an existing .env
if [ ! -f "$PROFILE_DIR/.env" ]; then
  [ -f "$REPO_DIR/.env.example" ] && cp "$REPO_DIR/.env.example" "$PROFILE_DIR/.env"
  chmod 600 "$PROFILE_DIR/.env" 2>/dev/null || true
fi

# 4. Skills
if [ -d "$REPO_DIR/skills" ]; then
  echo "==> Copying curated skills ($(find "$REPO_DIR/skills" -name SKILL.md | wc -l) skills)"
  cp -r "$REPO_DIR/skills/." "$PROFILE_DIR/skills/"
fi

# 5. Post-install reminders
echo
echo "==> Install complete. Next steps:"
echo "    1. Add your provider key:  edit $PROFILE_DIR/.env  (OPENCODE_GO_API_KEY=...)"
echo "    2. Verify identity:         hermes -p $PROFILE_NAME chat -q \"Who are you?\""
echo "       expect: My name is yolka."
echo "    3. Health check:            hermes doctor"
echo "    4. Toolchain (optional):    cd $REPO_DIR/docker && docker build -t yolka ."
echo "       or full VM:              cd $REPO_DIR/vm && vagrant up"
