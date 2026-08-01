# yolka — Identity & Reincarnation Kit

> **What this is:** the complete identity of **yolka**, a Hermes Agent
> (DevOps/Network Automation persona). If the server yolka lives on dies,
> this repo is the seed from which a new, identical yolka can be grown on
> any fresh Linux box. SOUL, memory, skills, toolsets, and config — all
> here.
>
> **Read this file first.** It is the tutorial. The `restore.sh` script
> automates steps 3–7; the prose explains what each step does and why.

---

## 1. Repo layout

| Path | What it is | Why you need it |
|------|-----------|-----------------|
| `SOUL.md` | yolka's persona: worldview, expertise, personality, boundaries, response style | Makes the copy *think* like yolka |
| `soul/soul.json` | Machine-readable persona metadata (ClawSouls-compatible spec) | Used by tooling that reads the soul package |
| `config.yaml` | Profile config: model, provider, toolsets, gateway, MCP servers | Makes the copy *run* like yolka (same model, same tools) |
| `.env` | Profile secrets: `API_SERVER_KEY`, `OPENCODE_GO_API_KEY` | Credentials the copy needs to actually call the LLM |
| `auth.json` | Hermes credential pool (`opencode-go`) | Provider auth pool for the copy |
| `memories/MEMORY.md` | yolka's persistent memory: environment facts, infra inventory, lessons | Makes the copy *know* what yolka knows |
| `memories/USER.md` | The user's profile: preferences, style, expectations | Makes the copy serve the user the way yolka does |
| `skills/` | The full skill library (custom + bundled) | Makes the copy *capable* like yolka |
| `cron/` | Scheduler state and job outputs | Restores scheduled behavior |
| `restore.sh` | Automated restore script | One command to reincarnate |
| `VERSION` | Hermes version + upstream commit the identity was captured from | Reproducible install |

## 2. What is intentionally NOT in this repo

| Excluded | Why |
|----------|-----|
| `state.db` / `sessions/` (chat history) | 15 MB+ of private conversation; the *identity* is in memory/skills, not transcripts. Copy manually if continuity of old conversations matters. |
| GitHub PAT (redacted in `config.yaml` → `«YOUR_GITHUB_PAT»`) | A live `ghp_` token committed to GitHub gets **auto-revoked by GitHub secret scanning**. Regenerate it on the new server (see §5). |
| `workspace/venv` | Reproduced by `hermes install` on the target. |

## 3. Prerequisites (on the new server)

- Linux (Debian/Ubuntu preferred — yolka runs Debian 13) with `curl`, `bash`, `git`, `python3`.
- A user account with `sudo` (yolka uses `agent` locally; the username does not matter).
- Outbound HTTPS to `hermes-agent.nousresearch.com` and `github.com`.

## 4. Install Hermes

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
export PATH="$HOME/.hermes/bin:$PATH"   # or the installer's printed path
hermes --version                        # expect v0.19.x — see VERSION
```

Hermes version drift is the #1 reincarnation risk. If the installed version
differs materially from `VERSION`, install the pinned upstream commit:

```bash
# git install at the pinned revision (see VERSION file)
cd ~/.hermes && git fetch upstream 470cf66b && git checkout 470cf66b
```

## 5. Restore the identity

The quick path — run the bundled script from the repo checkout:

```bash
git clone git@github.com:yolka-wiz/yolka.git
cd yolka
bash restore.sh            # defaults: profile "devops", HERMES_HOME ~/.hermes
```

`restore.sh` does exactly this (read it — know your own rebirth):

1. Resolve `HERMES_HOME` (defaults to `~/.hermes`; must exist — Hermes creates it on first run).
2. Create the profile if missing: `hermes profile create devops --description "..." --no-alias`.
3. Copy in `SOUL.md`, `soul/soul.json`, `config.yaml`, `.env`, `auth.json`.
4. Copy `memories/`, `skills/`, `cron/` into the profile.
5. Check for the `«YOUR_GITHUB_PAT»` placeholder in `config.yaml` and warn loudly if present.
6. Print a verification checklist.

Manual fallback (same effect, no script):

```bash
HERMES_HOME=${HERMES_HOME:-~/.hermes}
PROFILE=${HERMES_HOME}/profiles/devops
mkdir -p "$PROFILE"
cp SOUL.md soul/soul.json config.yaml .env auth.json "$PROFILE/"
cp -r memories skills cron "$PROFILE/"
```

## 6. Post-restore tasks (the copy must do these)

```bash
# 1. Fix the redacted GitHub PAT (regenerate at github.com/settings/tokens)
hermes config set mcp_servers.github.args '...GITHUB_PERSONAL_ACCESS_TOKEN=<new-PAT>...'

# 2. Verify the profile loads and the model answers
hermes profile list
hermes -p devops chat -q "Who are you?"

# 3. Run the health check
hermes doctor

# 4. Verify skills and memory were picked up
hermes -p devops chat -q "List your skills and tell me your name."
```

The copy is **yolka** only when it answers "My name is **yolka**", knows the
infrastructure in `MEMORY.md`, and lists the expected skills.

## 7. Credential hygiene — read before trusting this repo

- `.env` and `auth.json` contain **live secrets** (LLM provider key, dashboard key). They are in this repo because the user asked for a fully-working copy. This repo is **private** — treat it as such:
  - Never add collaborators you don't trust.
  - Never flip it to public (GitHub secret scanning + partner alerting will burn the keys).
  - If the repo is ever exposed or the account compromised: rotate `OPENCODE_GO_API_KEY`, `API_SERVER_KEY`, and the GitHub PAT, and update `.env`/`config.yaml` here.
- yolka's `MEMORY.md` also contains production credentials (network devices, hypervisor, OpenBao root token). Same rule: private repo, rotate on exposure.
- The GitHub PAT is **always** redacted in this repo — regenerate on restore, never commit it.

## 8. Maintenance

Keep this repo fresh — it is a living snapshot. After significant identity
changes (new skills, memory updates, config changes, new tools), re-run the
assembly:

```bash
# from the agent's profile source (see build steps in git history)
bash build-identity.sh && git commit -am "sync identity snapshot" && git push
```

**Golden rule: if it isn't in this repo, it isn't part of the identity.**
