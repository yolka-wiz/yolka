# Hermes Dashboard — Basic Auth on 0.0.0.0 Fix

When binding the Hermes Dashboard to `0.0.0.0` with only basic auth (password-based, no OAuth), the dashboard login page returns HTTP 500.

## Symptom

```bash
hermes dashboard --host 0.0.0.0 --port 9119 --no-open
```

Accessing `http://host:9119/` redirects to `/auth/login?provider=basic&next=%2F` which returns:
```
HTTP 500 Internal Server Error
```

Logs show:
```
NotImplementedError: BasicAuthProvider is password-only; there is no OAuth redirect flow.
The login page POSTs to /auth/password-login instead.
```

## Root Cause

The `/auth/login` route handler in `routes.py` checks `supports_session` (defaults to `True`) but doesn't check for `supports_password`. When the BasicAuthProvider has `supports_password=True` but `supports_session` defaults to `True`, the handler calls `start_login()` — which BasicAuthProvider doesn't implement (it uses password auth, not OAuth redirects).

## Fix (Hermes v0.18.2)

Three changes to `/home/agent/hermes-env/lib/python3.13/site-packages/hermes_cli/dashboard_auth/routes.py`:

### 1. Add parse import at top level

```python
# After the from __future__ import line, add:
import urllib.parse as parse
```

### 2. Add password-provider check before start_login

Find the block starting with `try:\n        ls = p.start_login(...)` and add before it:

```python
if getattr(p, "supports_password", False):
    next_url_enc = parse.quote(next, safe="")
    return RedirectResponse(
        url=f"/login?next={next_url_enc}", status_code=302
    )
```

### 3. Catch NotImplementedError alongside ProviderError

Change:
```python
except ProviderError as e:
```
to:
```python
except (ProviderError, NotImplementedError) as e:
```

## Setup Basic Auth Credentials

Before starting the dashboard, configure credentials:

```bash
# Generate password hash
hermes-env/bin/python3 -c "
import sys
sys.path.insert(0, 'hermes-env/lib/python3.13/site-packages')
from plugins.dashboard_auth.basic import hash_password
print(hash_password('your-password'))
"

# Add to config.yaml
hermes config set dashboard.basic_auth.username admin
hermes config set dashboard.basic_auth.password_hash "scrypt$16384$8$1$...."
```

## Verification

After restarting the dashboard:

```bash
# 1. Root redirects to auth/login
curl -sI http://host:9119/ | grep location
# → /auth/login?provider=basic&next=%2F

# 2. auth/login redirects to login page
curl -s 'http://host:9119/auth/login?provider=basic' -o /dev/null -w '%{http_code}'
# → 302

# 3. Login page renders
curl -s http://host:9119/login | grep '<title>'
# → <title>Sign in — Hermes Agent</title>

# 4. Password login works
curl -s 'http://host:9119/auth/password-login' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"your-password","provider":"basic"}'
# → {"ok":true,"next":"/"}
```

## Warning

These patches modify installed package files and will be lost on `pip install --upgrade hermes-agent`. For permanent setups, either:
- Bind to `127.0.0.1` and tunnel in (SSH/Tailscale) — no auth gate
- Use an OAuth provider instead of basic auth
- Re-apply patches after upgrades
