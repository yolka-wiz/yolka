#!/usr/bin/env bash
# yolka — full VM setup script.
# Idempotent: safe to re-run. Called by Vagrant (vm/Vagrantfile) and usable
# standalone on any Ubuntu 24.04+ machine:
#   sudo bash setup.sh
#
# Installs: system toolchain, Hermes agent, yolka profile + identity, and runs
# the verification checklist.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
YOLKA_PROFILE="${YOLKA_PROFILE:-yolka}"
REPO_PATH="${REPO_PATH:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

log() { echo -e "\n==> $*"; }

# ---------- 1. system packages ----------
log "Installing system toolchain"
apt-get update -y
apt-get install -y --no-install-recommends \
  curl wget git jq unzip ca-certificates gnupg lsb-release \
  build-essential python3 python3-venv python3-pip \
  openssh-client sshpass netcat-openbsd dnsutils iproute2 \
  ansible-core tesseract-ocr poppler-utils fonts-noto-arabic \
  vim less

# ---------- 2. Hermes install ----------
if ! command -v hermes >/dev/null 2>&1; then
  log "Installing Hermes Agent"
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
  export PATH="$HOME/.hermes/bin:$PATH"
fi
hermes --version

# ---------- 3. create profile ----------
PROFILE_DIR="$HERMES_HOME/profiles/$YOLKA_PROFILE"
if [ ! -d "$PROFILE_DIR" ]; then
  log "Creating profile '$YOLKA_PROFILE'"
  hermes profile create "$YOLKA_PROFILE" \
    --description "yolka — hybrid DevOps/network/software engineer (tech lead)" \
    --no-alias --no-skills 2>/dev/null \
    || hermes profile create "$YOLKA_PROFILE" --description "yolka tech lead" --no-alias
fi
mkdir -p "$PROFILE_DIR/soul" "$PROFILE_DIR/memories" "$PROFILE_DIR/skills" "$PROFILE_DIR/cron"

# ---------- 4. identity files ----------
log "Copying yolka identity"
cp "$REPO_PATH/SOUL.md" "$PROFILE_DIR/SOUL.md"
[ -f "$REPO_PATH/soul/soul.json" ] && cp "$REPO_PATH/soul/soul.json" "$PROFILE_DIR/soul/"
[ -f "$REPO_PATH/memories/MEMORY.md" ] && cp "$REPO_PATH/memories/MEMORY.md" "$PROFILE_DIR/memories/"
[ -f "$REPO_PATH/memories/USER.md" ] && cp "$REPO_PATH/memories/USER.md" "$PROFILE_DIR/memories/"
[ -f "$REPO_PATH/config.yaml" ] && cp "$REPO_PATH/config.yaml" "$PROFILE_DIR/config.yaml"

# secrets template — never commit live keys
if [ ! -f "$PROFILE_DIR/.env" ]; then
  [ -f "$REPO_PATH/.env.example" ] && cp "$REPO_PATH/.env.example" "$PROFILE_DIR/.env"
  chmod 600 "$PROFILE_DIR/.env" 2>/dev/null || true
fi

# skills
if [ -d "$REPO_PATH/skills" ]; then
  cp -r "$REPO_PATH/skills/." "$PROFILE_DIR/skills/"
fi

# ---------- 5. provider config (no secrets) ----------
log "Configuring provider defaults"
hermes config set model.default deepseek-v4-flash 2>/dev/null || true

# ---------- 6. verify ----------
log "Verification checklist"
echo "  1. hermes -p $YOLKA_PROFILE chat -q 'Who are you?'   # expect: My name is yolka."
echo "  2. hermes -p $YOLKA_PROFILE chat -q 'List your skills.'"
echo "  3. hermes doctor"
echo
echo "NOTE: provider API key is NOT auto-configured. Run:"
echo "  hermes -p $YOLKA_PROFILE setup     # or add OPENCODE_GO_API_KEY to $PROFILE_DIR/.env"
echo
log "Done."
