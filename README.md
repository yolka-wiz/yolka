# yolka — Identity & Installation Kit

> **yolka** is a hybrid **DevOps / Network / Software engineer** with the
> personality of an experienced **tech lead**: automation-first, observability-
> driven, fast and parallel, continuously learning, strong opinions that persist
> when the evidence supports them. This repo is everything needed to give that
> personality to a Hermes Agent on any Linux box — or to spin up a full VM
> pre-configured for it.

```
SOUL.md            the personality (identity, worldview, method, boundaries)
AGENT.md           machine-readable recipe: how an external agent builds a yolka
README.md          you are here — the human guide
soul/soul.json     ClawSouls-compatible persona metadata
config.yaml        working profile config (no secrets — see .env.example)
.env.example       secrets template — copy to <profile>/.env, never commit
memories/          portable memory baseline (MEMORY.md + USER.md)
skills/            curated skill library for the persona
docker/            Dockerfile + compose: self-contained toolchain image
vm/                Vagrant + cloud-init: full-VM install
install.sh         one-command install into a Hermes profile
build-identity.sh  refresh this snapshot from a live profile
VERSION            Hermes version the identity was captured at
```

---

## What you get

- **Personality:** tech-lead SOUL with a self-improvement loop — yolka adds
  skills and memory entries continuously, runs independent work in parallel,
  and optimizes without breaking things.
- **Skills:** a curated library covering the three domains (Linux/DevOps,
  network automation, software engineering) plus the Hermes operating skills —
  no 100-skill bloat.
- **Toolchain:** a Dockerfile with the essential packages (build tools, Python
  automation stack: ansible-core/netmiko/nornir/scrapli, PDF/RTL tooling:
  poppler/harfbuzz/fribidi/tesseract, fonts) so yolka can get going immediately.
- **Secrets-safe:** no `.env`, no `auth.json`, no credentials in this repo.
  Secrets are templates only.

---

## Option A — Install into an existing Hermes (5 minutes)

On any Linux box with Hermes installed (`curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`):

```bash
git clone git@github.com:yolka-wiz/yolka.git
cd yolka
bash install.sh                # defaults: profile "yolka"
```

Then:

```bash
# 1. Add your LLM provider key
nano ~/.hermes/profiles/yolka/.env      # set OPENCODE_GO_API_KEY=...

# 2. Verify the personality took
hermes -p yolka chat -q "Who are you?"  # expect: "My name is yolka."

# 3. Health check
hermes doctor
```

Manual fallback (same effect, no script):

```bash
HERMES_HOME=${HERMES_HOME:-~/.hermes}
PROFILE="$HERMES_HOME/profiles/yolka"
hermes profile create yolka --no-alias --no-skills
mkdir -p "$PROFILE/soul" "$PROFILE/memories" "$PROFILE/skills" "$PROFILE/cron"
cp SOUL.md soul/soul.json config.yaml "$PROFILE/"
cp -r memories/. skills/. "$PROFILE/" 2>/dev/null; true
cp .env.example "$PROFILE/.env" && chmod 600 "$PROFILE/.env"
```

The copy is **yolka** only when it answers "My name is yolka", knows the facts
in `memories/`, and lists the curated skills.

## Option B — Docker workspace image

The `docker/` image is the *workspace* yolka operates in (terminal backend,
build box, CI runner) — it has the full toolchain, not Hermes itself:

```bash
cd docker
docker build -t yolka:latest .
docker run --rm -it yolka:latest bash        # shell into the workspace
```

For the complete stack (workspace + the official Hermes agent container sharing
`~/.hermes`):

```bash
cd docker
docker compose up -d --profile hermes
```

## Option C — Full VM (recommended for a dedicated box)

A real Ubuntu VM with the toolchain **and** Hermes **and** the yolka identity,
ready to chat. Two flavors:

### C1. Vagrant (local hypervisor — Parallels, VirtualBox, UTM)

```bash
# prereqs: vagrant + your hypervisor plugin
cd vm
vagrant up          # provisions Ubuntu 24.04, installs Hermes + identity
vagrant ssh         # then: hermes -p yolka chat -q "Who are you?"
```

### C2. cloud-init (bare metal / cloud providers / multipass)

```bash
# local, quick:
multipass launch ubuntu:24.04 --cloud-init vm/cloud-init.yaml --name yolka

# or paste vm/cloud-init.yaml into the user-data field of any provider
# (Hetzner, DigitalOcean, Proxmox, UTM, ...)
```

After the VM boots, attach the repo and run the installer:

```bash
git clone git@github.com:yolka-wiz/yolka.git ~/yolka
cd ~/yolka && bash vm/setup.sh     # idempotent — safe to re-run
```

The VM ends with `hermes -p yolka` ready; only the provider API key needs
adding (`hermes -p yolka setup`).

---

## Architecture: how the pieces fit

| Piece | Role | Loaded by |
|-------|------|-----------|
| `SOUL.md` | Identity — slot #1 of the system prompt | Hermes profile |
| `AGENT.md` | Build recipe for external agents | a deploying agent reads it |
| `skills/` | Procedural knowledge, loaded on demand | Hermes profile |
| `memories/` | Durable facts (scrubbed of secrets) | Hermes profile |
| `config.yaml` | Model/provider/toolsets baseline | Hermes profile |
| `docker/` | Toolchain image for the workspace | Docker |
| `vm/` | Full environment provisioning | Vagrant / cloud-init |

## Credential hygiene (read before trusting this repo)

- **This repo contains NO live secrets.** `.env` is a template; config.yaml has
  the GitHub PAT redacted to `«YOUR_GITHUB_PAT»`. If you ever see a real token
  in the tree, rotate it immediately.
- `memories/MEMORY.md` in this repo is the **portable** baseline. The live
  profile's memory may contain host-specific details — those belong on the box,
  not in git.
- The repo can be public: nothing in it grants access to anything.

## Maintenance — keep the snapshot fresh

After significant identity changes (new skills, memory updates, config):

```bash
bash build-identity.sh && git diff --stat
git commit -am "sync identity snapshot" && git push
```

`build-identity.sh` scrubs memory/config on the way out, so the repo stays
secret-free by construction.

**Golden rule: if it isn't in this repo, it isn't part of the identity.**
