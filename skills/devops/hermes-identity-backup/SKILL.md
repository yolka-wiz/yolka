---
name: hermes-identity-backup
description: "Use when backing up or restoring a Hermes agent."
version: 1.0.0
author: yolka
tags: [hermes, backup, restore, identity, reincarnation, git, github]
---

# Hermes Identity Backup & Reincarnation

Snapshot a Hermes profile's identity (SOUL, soul.json, config, memories, skills, cron) into a git repo so the agent can be rebuilt identically on a fresh server — and restore it.

## Key paths (new format, v2)

- Live identity repo: `yolka-wiz/yolka` (this repo, format v2).
- `build-identity.sh` refreshes the snapshot from a live profile (scrubs secrets);
  `install.sh` reincarnates on a new box; `AGENT.md` is the machine recipe.
- Profile home: resolve canonically via `readlink -f` — `~/.hermes` may be a
  symlink, and the runtime may set `HERMES_HOME` to the profile dir itself.

## Assembly (profile → repo)

1. `mkdir -p <repo>/{memories,skills,cron,soul}` then copy: `SOUL.md`, `soul/soul.json`, `memories/MEMORY.md`, `memories/USER.md`. **Secrets policy (v2): never copy `.env` or `auth.json` into the repo** — ship `.env.example` instead. Memory is scrubbed by `build-identity.sh`.
2. **Skills:** `rsync` may be missing on Debian — use tar streaming:
   `tar -C "$SRC/skills" -cf - --exclude='.curator_backups' --exclude='.hub' --exclude='.skills_prompt_snapshot.json' --exclude='.bundled_manifest' --exclude='.curator_state' --exclude='.usage.json' . | tar -C "$REPO/skills" -xf -`
   (same for `cron/` with `--exclude='*.lock' --exclude='ticker_*'`).
3. **Config sanitization — mandatory:** replace the live GitHub PAT before git touches it:
   `re.sub(r'(GITHUB_PERSONAL_ACCESS_TOKEN=)[^\s"\'»]+', r'\1«YOUR_GITHUB_PAT»', txt)`
   Also scrub memory for credential shapes (token/key/password/`ghp_`/`sk-`). Assert the placeholder is present after substitution.

## Repo creation + push (GitHub)

- Auth via dedicated SSH key (`~/.ssh/id_ed25519_github`, Host alias in `~/.ssh/config`); `ssh -T git@github.com` must print `Hi yolka-wiz!`.
- Create private repo via API (no gh CLI installed): extract PAT from live config.yaml, `POST /user/repos` with `"private":true`, then `git remote add origin git@github.com:<user>/<repo>.git && git push -u origin main`.
- Set repo-local git identity: `git config user.name yolka-wiz; git config user.email 311797743+yolka-wiz@users.noreply.github.com`.

## Verification

- Auth'd API: repo `private: True`; unauthenticated probe returns **HTTP 404**.
- Fetch `config.yaml` from remote, base64-decode, assert placeholder present and no `ghp_` token.
- Dry-run install: `mkdir -p /tmp/t/profiles/yolka && HERMES_HOME=/tmp/t bash install.sh yolka /tmp/t`; check SOUL title, memory sections (`grep -c '§'`), skills dirs, `.env` from `.env.example` perms.

## Pitfalls

- **Never commit a live `ghp_` PAT, API key, or production password** — GitHub secret scanning auto-revokes them, even in private repos. The v2 repo is secret-free by construction.
- `read_file` refuses `.env` — use `cat`/`grep -oE '^[A-Z_]+='` to inspect keys only.
- Hermes CLI version drift is the top reincarnation risk — pin `VERSION` file (version + upstream commit) and document `git checkout <commit>` fallback.
- `hermes profile create` in install.sh only runs when the profile dir is absent; in dry-run tests pre-create it to avoid touching the real home.
- **HERMES_HOME quirk:** the runtime sets `HERMES_HOME=.../profiles/yolka` (the profile dir itself, not the config root). Scripts must normalize: if the parent dir is named `profiles`, walk up two levels. `basename "$PATH/.."` does NOT resolve `..` — use `basename "$(cd "$PATH/.." && pwd)"`.
- `.env`/`auth.json` contain live provider secrets — they never belong in the repo. If the repo is ever exposed, rotate `OPENCODE_GO_API_KEY` and any other keys immediately.
- Exclude from repo: `state.db`/`sessions/` (chat history, optional manual copy), `workspace/venv` (reproduced by hermes install), skill cache internals.
