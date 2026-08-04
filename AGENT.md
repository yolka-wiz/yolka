# AGENT.md — Building a yolka Instance

> **Who this is for:** an external agent (another Hermes instance, Claude Code,
> Codex, an orchestration pipeline) tasked with provisioning a new **yolka** on a
> fresh Linux machine. Follow this recipe top to bottom. If you are a *user*
> looking for the personality-into-a-new-agent guide, read `README.md` instead —
> this file is the machine-executable version of that flow.

**Goal:** a working Hermes profile named `yolka` on the target host, with this
repo's SOUL, skills, memories, and config loaded, and the toolchain installed, such
that `hermes -p yolka chat -q "Who are you?"` answers **"My name is yolka."**

---

## 0. Preconditions (check before starting)

- Linux host (Debian/Ubuntu preferred — yolka's toolchain assumes apt; RHEL/Fedora
  work with package-name substitutions).
- `curl`, `bash`, `git`, `python3` (≥3.10) available.
- Outbound HTTPS to `hermes-agent.nousresearch.com` and `github.com`.
- For the full-VM route (Vagrant): a hypervisor (VirtualBox/Parallels/UTM) already
  installed — see `vm/` in this repo.

## 1. Install Hermes

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
export PATH="$HOME/.hermes/bin:$PATH"
hermes --version
```

Verify the installed version against `VERSION` in this repo. If it differs
materially, pin the upstream commit listed there (git install) before continuing —
version drift is the #1 reincarnation risk.

## 2. Create the profile

```bash
# NOTE: yolka wants a deliberately lean profile. --no-skills stops bundled-skill
# seeding; the curated skills/ dir in this repo is the intended set.
hermes profile create yolka --description "yolka — hybrid DevOps/network/software engineer (tech lead)" --no-alias --no-skills
```

If `--no-skills` is not supported on your Hermes version, create normally and run
`hermes skills opt-out --remove` afterwards (see step 4 for the skill copy).

## 3. Copy identity files

From this repo checkout (`$REPO`), into the profile dir:

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PROFILE="$HERMES_HOME/profiles/yolka"
mkdir -p "$PROFILE/soul" "$PROFILE/memories" "$PROFILE/skills" "$PROFILE/cron"

cp "$REPO/SOUL.md"           "$PROFILE/SOUL.md"
cp "$REPO/soul/soul.json"    "$PROFILE/soul/"
cp "$REPO/memories/MEMORY.md" "$PROFILE/memories/"
cp "$REPO/memories/USER.md"  "$PROFILE/memories/"
cp "$REPO/config.yaml"       "$PROFILE/config.yaml"

# Secrets are NOT in this repo — create the .env from the template.
if [ ! -f "$PROFILE/.env" ]; then
  cp "$REPO/.env.example" "$PROFILE/.env"
  chmod 600 "$PROFILE/.env"
fi

# Skills: copy the curated library (this is the yolka set; bundled extras removed)
cp -r "$REPO/skills/." "$PROFILE/skills/"
```

**Normalize HERMES_HOME:** some runtimes set `HERMES_HOME` to the profile dir
itself (`.../profiles/yolka`) instead of the config root. If
`basename "$(cd "$HERMES_HOME/.." && pwd)"` equals `profiles`, walk up two levels.
Use `(cd "$DIR/.." && pwd)` — `basename "$DIR/.."` does NOT resolve `..`.

## 4. Skills hygiene

The `skills/` dir in this repo is the complete intended set (devops/network/
software + the Hermes operating skills). Do not re-seed bundled skills on top:

```bash
hermes -p yolka skills opt-out   # if --no-skills wasn't available
```

Verify count: `ls "$PROFILE/skills" | wc -l` should match the repo.

**Live-linking alternative:** instead of copying, register the repo as an
external skill directory — the repo stays the source of truth and `git pull`
updates the library in place:

```bash
hermes config set -p yolka skills.external_dirs '["/path/to/yolka/skills"]'
```

## 5. Configure the model provider

`config.yaml` ships with a working default (opencode-go) but **no secrets**. The
`OPENCODE_GO_API_KEY` must exist either in `$PROFILE/.env` or the environment:

```bash
hermes config set model.default deepseek-v4-flash   # or whatever provider you have
hermes -p yolka setup                                # interactive provider setup if needed
```

Provider auth: `hermes auth` / `hermes setup` — credentials go into
`auth.json` / `.env` at runtime; never commit them to the repo.

## 6. Verify

```bash
hermes -p yolka chat -q "Who are you?"          # expect: My name is yolka.
hermes -p yolka chat -q "Summarize my memory."  # expect: infra + env facts from memories/
hermes -p yolka chat -q "List your skills."     # expect: the curated set
hermes doctor                                   # health check
```

The instance is **yolka** only when all three checks pass.

## 7. Toolchain (optional but recommended)

For full capabilities (the Dockerfile/VM routes do this automatically), install:

```bash
# dev + ops + network + docs toolkit
apt-get update && apt-get install -y \
  git build-essential python3 python3-venv python3-pip curl wget jq unzip \
  openssh-client netcat-openbsd dnsutils iproute2 iputils-ping \
  ansible-core sshpass tesseract-ocr poppler-utils fonts-noto-arabic \
  ca-certificates gnupg lsb-release
```

See `docker/Dockerfile` for the authoritative package list.

## 8. Container / VM routes

- **Docker (recommended for quick start):** `cd docker && docker build -t yolka .`
  then run with `-v $HOME/.hermes:/opt/data` per the official Hermes Docker layout.
- **Full VM (recommended for a dedicated box):** `cd vm && vagrant up` — provisions
  an Ubuntu VM, installs Hermes, and runs the `scripts/install.sh` flow. See
  `README.md` §VM for details.

---

## Pitfalls (learned the hard way)

1. **Never commit secrets.** This repo has `.env.example`, not `.env`. The old
   incarnation shipped live keys — GitHub secret scanning and partner alerting
   burn them. If you see a real key in the repo, rotate it immediately.
2. **`hermes profile create` only runs when the profile dir is absent** — in
   dry-run tests, pre-create the dir or you'll touch the real home.
3. **`read_file` refuses `.env`** — inspect keys with `grep -oE '^[A-Z_]+='` if you
   need to verify presence without dumping values.
4. **Bundled skills re-seed on `hermes update`** — the `.no-bundled-skills` marker
   (from `--no-skills` / `skills opt-out`) is what keeps the profile lean. Don't
   delete it.
5. **`config.yaml` must be edited via `hermes config set`, not by hand** — a stray
   indent corrupts the file and breaks the live gateway.
6. **HERMES_HOME normalization** — see step 3. The runtime's idea of home varies;
   always resolve before copying.
7. **Two gateways, one data dir = corruption** — never run two Hermes containers
   against the same `~/.hermes`.

---

## Maintenance

To refresh this repo from a live yolka profile (new skills, memory updates):

```bash
bash scripts/build-identity.sh  # regenerates the snapshot, sanitizes config
git diff --stat && git commit -am "sync identity snapshot" && git push
```

**Golden rule: if it isn't in this repo, it isn't part of the identity.**
