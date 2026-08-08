---
name: hermes-web-tools
description: "Use when Hermes web search/extract backends break or fail."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, web, search, extract, backend, troubleshooting, ddgs]
    related_skills: [hermes-profile-provisioning, dev-toolchain-provisioning]
---

# Hermes Web Tools (search / extract backends)

Use when `web_search` or `web_extract` fails on a Hermes agent, or when configuring
which backend a profile uses for web research. Both search and extraction are plugin
capabilities; failures are almost always **setup state**, never "the tool is broken".

## How the tooling is wired

- Plugins live in `~/.hermes/hermes-agent/plugins/web/<provider>/` — each has a
  `provider.py` + `plugin.yaml`. The plugin tree IS the inventory of available backends.
- Active profile backend: `~/.hermes/profiles/<name>/config.yaml`:
  ```yaml
  web:
    backend: ddgs
    use_gateway: false
  ```
- Search backends (keyless): `ddgs` (DuckDuckGo). Others: brave_free, searxng, xai.
- Extract-capable backends: `firecrawl`, `tavily`, `exa`, `parallel` — **all require
  API keys** (env vars `FIRECRAWL_API_KEY`, `TAVILY_API_KEY`, `EXA_API_KEY`,
  `PARALLEL_API_KEY`). Check `env`, `~/.hermes/.env`, profile `.env` before assuming
  one exists.

## Fixes

### web_search: "ddgs package is not installed — run `pip install ddgs`"

The web plugin imports `ddgs` from the **Hermes application venv**, not the profile
venv and not any workspace venv:

```bash
~/.hermes/hermes-agent/venv/bin/pip install ddgs
~/.hermes/hermes-agent/venv/bin/python -c "import ddgs; print(ddgs.__file__)"   # verify
```

### web_extract: "ddgs is a search-only backend... Set web.extract_backend to firecrawl, tavily, exa, or parallel"

Extraction is a separate capability. Without a keyed backend configured, set one:
```bash
hermes config set web.extract_backend <firecrawl|tavily|exa|parallel>
```
or provide the matching API key in the environment. With no keys, use the keyless
fallback below instead of declaring extraction dead.

## Keyless extraction fallback

`web_extract` can be unavailable while raw HTTP is perfectly fine:
```bash
curl -sSL -m 20 -o /tmp/page.md https://raw.githubusercontent.com/<owner>/<repo>/main/README.md
```
- Prefer raw/plain-text URLs (raw.githubusercontent, docs markdown files).
- Add `-x socks5h://<host>:<port>` when the target blocks direct egress.
- `curl -I` (HEAD) lies on API endpoints (403/405) — probe with GET.

## Pitfalls

- **Never conclude "web tools don't work"** from a missing-package or missing-key
  error. The fix is `pip install ddgs` into the app venv, or wiring a key. Harden the
  fix, not the refusal.
- **Install into the APP venv** (`~/.hermes/hermes-agent/venv`), which is Python 3.11
  and separate from profile/workspace venvs. Installing into the wrong venv leaves the
  tool broken and looks like a successful fix.
- **Extract backends are paid/keyed by design** — a profile with only `backend: ddgs`
  has working search but no extract. Plan for the curl fallback or a key when the task
  needs page content.
- **Plugin providers list which are keyed**: read `<provider>/plugin.yaml` before
  choosing a backend.
