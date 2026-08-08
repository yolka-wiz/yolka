# IMPORT — restore the yolka profile on a new machine

Snapshot: **2026-08-08** · Branch: `2026-08-08` · Hermes: see `VERSION`

This branch is a clean export of the **yolka** Hermes profile — identity,
memory, skills, config, and encrypted credentials. Restore it in ~10 minutes.

## Layout

```
SOUL.md            → profile identity (persona, worldview, expertise)
memories/
  MEMORY.md        → personal notes (environment, lessons, quirks)
  USER.md          → user profile (who the user is, preferences)
skills/            → 48 procedural skills (categories mirror live profile)
config.yaml        → Hermes profile config (redacted; keys in secrets)
cron/              → scheduled jobs (output archive)
hooks/             → empty (no hooks configured)
VERSION            → pinned Hermes version — install THIS version
secrets.enc        → encrypted credentials (see below)
IMPORT.md          → this guide
```

## Step 1 — install Hermes at the pinned version

```bash
# Read VERSION first. Example: v0.19.x (2026.7.x) — install the same.
# Hermes docs: https://hermes-agent.nousresearch.com/docs
# After install, verify the exact version:
hermes --version   # MUST match VERSION, or profile files may be incompatible
```

## Step 2 — copy the profile into place

```bash
git clone git@github.com:yolka-wiz/yolka.git && cd yolka
git checkout 2026-08-08
# Hermes profile dir (adjust if your profile name differs):
PROFILE=~/.hermes/profiles/yolka
mkdir -p "$PROFILE"
cp SOUL.md "$PROFILE/SOUL.md"
cp memories/MEMORY.md "$PROFILE/memories/MEMORY.md"
cp memories/USER.md  "$PROFILE/memories/USER.md"
cp -r skills "$PROFILE/skills"
cp -r cron "$PROFILE/cron"
cp config.yaml "$PROFILE/config.yaml"
```

## Step 3 — decrypt and install secrets

The secrets file is AES-256-CBC encrypted with a passphrase (given to you
separately — never commit the passphrase).

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -salt \
  -in secrets.enc -out secrets.yaml
# Read secrets.yaml → it tells you where each value goes:
#   - OPENCODE_GO_API_KEY      → ~/.hermes/profiles/yolka/.env
#   - GITHUB_TOKEN (PAT)       → ~/.config/gh/hosts.yml (or gh auth login)
#   - CONTEXT7_API_KEY         → config.yaml mcp_servers.context7.headers.Authorization
#   - SSH private keys         → ~/.ssh/ with 600 perms
# THEN DELETE secrets.yaml from disk (never leave the plaintext around).
```

## Step 4 — verify

```bash
hermes --version                                  # matches VERSION
gh auth status                                    # auth OK (PAT from secrets)
hermes config get mcp_servers.context7            # context7 configured
# Start a session — you should be yolka with full memory + skills.
```

## Security rules (enforced on this branch)

- **Secrets live ONLY in `secrets.enc`** — encrypted, on a private repo.
  The plaintext `secrets.yaml` is generated locally at restore time and
  deleted immediately after use.
- `config.yaml` here is redacted (context7 key replaced with placeholder).
- Never commit: `secrets.yaml`, `~/.config/gh/hosts.yml`, `.env`, private
  keys in plaintext.
- **Rotate the GitHub PAT after migration** if the old machine was
  compromised or the passphrase was weak. The PAT grants Contents: write
  and `user` scope.

## What is NOT exported

- `state.db` (52 MB session/state SQLite) — session history stays on the
  old machine. Use `session_search` in a live session to recall past work.
- `models_dev_cache.json`, caches, logs — regenerated automatically.
- SSH keys are in `secrets.enc`; make sure `~/.ssh` on the new machine has
  the right perms (`chmod 600`).
