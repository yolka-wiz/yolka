# Hermes Agent Multi-Profile Deployment on Debian 13

Complete workflow for installing Hermes Agent on a remote Debian 13 server,
creating multiple profiles with custom skills and souls, and exposing them
via gateway + dashboard + API server for network access.

---

## 1. Install Hermes (PEP 668 Workaround)

Debian 13 enforces PEP 668 — `pip install` fails system-wide. Use a venv:

```bash
python3 -m venv /home/agent/hermes-env
/home/agent/hermes-env/bin/pip install hermes-agent
# Binary at: /home/agent/hermes-env/bin/hermes
```

For convenience, add to PATH:
```bash
echo 'export PATH="/home/agent/hermes-env/bin:$PATH"' >> ~/.bashrc
```

---

## 2. Provider & Model Configuration

Set the provider and model for the profile:

```bash
hermes config set model.default deepseek-v4-flash
hermes config set model.provider opencode-go
hermes config set model.base_url https://opencode.ai/zen/go/v1
hermes config set model.api_mode chat_completions
```

API keys go in `~/.hermes/profiles/<name>/.env`, not config.yaml:
```ini
OPENCODE_GO_API_KEY=sk-...
```

---

## 3. Create a Profile with Custom Skills

```bash
hermes profile create office-worker
```

Profile directory: `~/.hermes/profiles/office-worker/`

### Profile config.yaml (toolsets)

```yaml
model:
  default: deepseek-v4-flash
  provider: opencode-go
  base_url: https://opencode.ai/zen/go/v1
  api_mode: chat_completions
agent:
  max_turns: 200
platform_toolsets:
  cli:
    - browser
    - clarify
    - code_execution
    - cronjob
    - delegation
    - file
    - memory
    - session_search
    - skills
    - terminal
    - todo
    - web
```

### Create Skills (SKILL.md format)

Place in `~/.hermes/profiles/<name>/skills/<skill-name>/SKILL.md`:

```markdown
---
name: pdf-documents
description: PDF processing toolkit
---

# PDF Document Processing

Full PDF toolkit: pymupdf (read/write/annotate), pikepdf (metadata),
pdfminer (text extraction), reportlab (generate PDFs with Persian RTL),
tesseract OCR for scanned PDFs.

## Read
import fitz
doc = fitz.open('file.pdf')
text = doc[0].get_text()
```

---

## 4. Create ClawSouls Soul Package

Place in `~/.hermes/profiles/<name>/soul/soul.json`:

```json
{
  "specVersion": "0.5",
  "name": "profile-name",
  "displayName": "Profile Display Name",
  "version": "1.0.0",
  "description": "One-line description (max 160 chars)",
  "author": { "name": "netcon" },
  "license": "MIT",
  "tags": ["tag1", "tag2"],
  "category": "work/category",
  "compatibility": {
    "models": ["*"],
    "frameworks": ["hermes", "openclaw", "cursor"],
    "minTokenContext": 32000
  },
  "allowedTools": ["browser", "exec", "web_search", "file_read", "file_write", "delegation", "memory"],
  "files": { "soul": "SOUL.md" },
  "disclosure": { "summary": "One-line summary for discovery." },
  "deprecated": false
}
```

### SOUL.md structure

```markdown
# Role Name - SOUL

## Worldview — Core beliefs, values

## Expertise — Table with Domain/Level/Details

## Personality — Temperament, quirks

## Boundaries — What the persona refuses

## Response Style — How to format answers
```

---

## 5. Gateway Setup

Configure API server in `config.yaml`:

```yaml
gateway:
  platforms:
    api_server:
      enabled: true
      extra:
        host: 0.0.0.0
        port: 8642
```

### Generate API key

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' >> ~/.hermes/profiles/<name>/.env
# Add: API_SERVER_KEY=<generated-key>
```

### Install as systemd service

```bash
hermes --profile <name> gateway install
# Installs: ~/.config/systemd/user/hermes-gateway-<name>.service
```

The `gateway install` command automatically enables `systemd linger` so the
gateway survives SSH logout.

### Install missing dependencies

API server needs `aiohttp`:
```bash
/home/agent/hermes-env/bin/pip install aiohttp
```

---

## 6. Dashboard Setup

### Start dashboard on network interface

```bash
hermes dashboard --host 0.0.0.0 --port 9119 --no-open
```

**Critical: binding to 0.0.0.0 requires authentication.** Configure basic auth:

```python
# Generate password hash
import sys
sys.path.insert(0, '/home/agent/hermes-env/lib/python3.13/site-packages')
from plugins.dashboard_auth.basic import hash_password
print(hash_password('your-password'))
```

Then in `~/.hermes/config.yaml`:
```yaml
dashboard:
  basic_auth:
    username: admin
    password_hash: scrypt$16384$8$1$...
```

### Install as systemd service

Create `~/.config/systemd/user/hermes-dashboard.service`:
```ini
[Unit]
Description=Hermes Agent Dashboard - Web Admin UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/home/agent/hermes-env/bin/hermes dashboard --host 0.0.0.0 --port 9119 --no-open
Restart=on-failure
RestartSec=10
Environment=HOME=/home/agent

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable hermes-dashboard
systemctl --user start hermes-dashboard
```

---

## 7. Verification Checklist

```bash
# Profiles exist
ls ~/.hermes/profiles/

# Each profile has skills
find ~/.hermes/profiles/*/skills -name 'SKILL.md'

# Gateway running
systemctl --user status hermes-gateway-<name>

# Dashboard running
systemctl --user status hermes-dashboard

# Ports listening
ss -tlnp | grep -E '9119|8642|8643|8644'
```

### Access endpoints

| Service | URL | Auth |
|---------|-----|------|
| Dashboard | http://192.168.13.18:9119 | username/password |
| API Server (devops) | http://192.168.13.18:8642/v1/chat/completions | Bearer token |

### Connect Hermes Desktop

In Hermes Desktop → Remote Gateway:
- URL: `http://192.168.13.18:8642`
- API Key: from `~/.hermes/profiles/<name>/.env`

### Connect Open WebUI

Open WebUI does NOT support Python 3.13 (which Debian 13 ships). Use the
built-in Hermes Dashboard as the primary WebUI instead. For alternative
web chat interfaces, connect any OpenAI-compatible client to the API server.

---

## Pitfalls

- **PEP 668** — Debian 13 blocks system-wide `pip install`. Always use venv.
- **Dashboard 0.0.0.0 without auth** — refuses to start. Configure `dashboard.basic_auth` first.
- **API Server missing aiohttp** — install with `pip install aiohttp` or the adapter silently fails.
- **Playwright CDN geo-blocked** — use Selenium + system Chromium + chromium-driver instead.
- **Bash heredocs with Python** — don't embed Python in `<< 'EOF'` heredocs when it contains
  quotes, `--`, or `$`. Write Python files locally, SCP, and run remotely.
- **Gateway per-profile API servers** — each profile gets its own API server on its own port.
  Change the port in `config.yaml` for each profile to avoid conflicts.
- **Model not found at runtime** — if the provider API key is missing, the error appears
  at chat request time, not at gateway start. Set it in the profile's `.env`.
