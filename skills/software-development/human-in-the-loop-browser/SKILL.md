---
name: human-in-the-loop-browser
description: "Browse the web via Hermes's built-in browser tools, with human-in-the-loop fallback for login pages, CAPTCHAs, and auth walls — pops up a visible browser window for the user to solve, then continues automation."
version: 1.1.0
author: Hermes Agent
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [browser, playwright, captcha, login, human-in-the-loop, auth, automation]
    related_toolsets: [browser, clarify]
---

# Human-in-the-Loop Browser Browsing

A workflow skill for browsing the web through Hermes's built-in browser tools, with automatic fallback to a **visible browser window** when the agent encounters login pages, CAPTCHAs, OAuth redirects, or any auth wall that needs human intervention.

## How It Works

```
Agent identifies a URL to browse
  ↓
Navigate using browser_navigate (works headless normally)
  ↓
browser_snapshot detects auth wall / login form / CAPTCHA
  ↓  (or snapshot is ambiguous — use browser_vision to inspect a screenshot)
Agent calls clarify() to alert the user
  ↓
User opens the already-running visible browser window, logs in / solves CAPTCHA
  ↓
User confirms via clarify()
  ↓
Agent re-snapshots and continues automation from the authenticated state
```

## Prerequisites

### 1. A visible Chromium browser with remote debugging

The agent needs to connect via **Chrome DevTools Protocol (CDP)** to a browser window you can see and interact with.

**Option A — Launch a fresh visible instance (recommended):**

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-hermes

# Linux
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-hermes

# Windows (PowerShell)
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\temp\chrome-hermes

# Windows (cmd)
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\temp\chrome-hermes
```

**Option B — Use an existing Chrome window:**

1. Close all Chrome windows
2. Re-launch with `--remote-debugging-port=9222` (as above)
3. The browser window is fully visible and interactive

**Option C — Use Edge or Brave instead:**

Both Microsoft Edge and Brave support CDP on the same port. If Chrome isn't installed:

```bash
# Windows — Edge
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir=C:\temp\edge-hermes

# macOS — Edge
/Applications/Microsoft\ Edge.app/Contents/MacOS/Microsoft\ Edge --remote-debugging-port=9222 --user-data-dir=/tmp/edge-hermes

# Linux — Brave
brave-browser --remote-debugging-port=9222 --user-data-dir=/tmp/brave-hermes
```

> ⚠️ **Important:** A Chromium-based browser (Chrome, Edge, Brave) is required. Firefox and Safari do NOT support CDP. If no browser is installed, see the **Headless Fallback** section below.

> ⚠️ **Chromium download geo-blocking:** Google's `chrome-for-testing` CDN and Playwright's CDN both return 403/AccessDenied from certain geographic regions. If `agent-browser install` or `npx playwright install chromium` fails with "Access denied" / "not available in your location", you cannot auto-download Chromium headlessly. Install a desktop browser (Chrome, Edge, or Brave) manually as shown above — that bypasses the CDN restriction entirely.

### 2. Connect Hermes to the visible browser

Tell Hermes to route all browser tools through the visible browser's CDP endpoint:

```
/browser connect ws://127.0.0.1:9222/devtools/browser/...
```

Or set it persistently in config:
```bash
hermes config set browser.cdp_url ws://127.0.0.1:9222
```

After connecting, run `browser_snapshot` to verify the connection works.

### 3. Enable the browser and clarify toolsets

```bash
hermes tools enable browser
hermes tools enable clarify
```

## Workflow Steps (for the Agent)

### Step 1 — Navigate normally

```python
result = browser_navigate(url="https://example.com/login", task_id="browse_session")
```

The browser window is visible on the user's screen — they can see the page load in real time.

### Step 2 — Detect auth walls, login forms, and CAPTCHAs

After navigating, inspect the page with `browser_snapshot`. Look for these signals:

**Login form indicators:**
- Page text contains: "sign in", "log in", "login", "sign in with", "continue with Google", "continue with GitHub", OAuth provider buttons
- Form fields: `input[type="password"]`, `input[name="email"]`, `input[name="login"]`
- Buttons labeled "Sign In", "Log In", "Continue", "Authorize"

**CAPTCHA indicators:**
- "I'm not a robot", "Verify you're human", "captcha", "reCAPTCHA", "hCaptcha", "turnstile", "challenge"
- `iframe` elements from `recaptcha.net`, `hcaptcha.com`, `challenges.cloudflare.com`, `turnstile`
- The page has an iframe with "challenge" or "captcha" in its URL or title

**Auth wall / OAuth indicators:**
- URL contains: `login`, `auth`, `oauth`, `authorize`, `signin`, `sso`, `saml`
- Page title contains: "Sign in", "Log in", "Authorize", "Authentication"
- Redirect chains: the page you navigated to redirected to a different domain's auth page

**Detection heuristics (use these with both snapshot text and URL analysis):**

```python
SIGNALS = {
    "login_form": ["sign in", "log in", "password", "email address", "username",
                   "input[type='password']", "login button", "sign-in"],
    "captcha": ["i'm not a robot", "verify you're human", "recaptcha",
                "hcaptcha", "turnstile", "cloudflare challenge",
                "security check", "verify your identity"],
    "oauth": ["sign in with google", "sign in with github", "sign in with",
              "continue with", "authorize", "oauth"],
    "auth_wall_url": ["login", "auth", "oauth", "authorize", "sso", "saml",
                      "signin", "logon", "authenticate"],
}
```

### Step 3 — Ask the user for help via clarify

When you detect a login page or CAPTCHA, **do NOT** try to fill in credentials or solve it yourself. Instead:

```python
# For login pages:
clarify(
    question="I've reached a login page at [URL]. Please sign in using the visible browser window that opened. Once you've logged in and are on the post-login page, reply 'done'.",
    choices=["I've logged in", "This isn't a login page, continue anyway", "Skip this page, navigate somewhere else"]
)

# For CAPTCHAs:
clarify(
    question="A CAPTCHA / bot-detection challenge is blocking the page at [URL]. Please solve it in the visible browser window. Once you've passed the challenge and are on the target page, reply 'done'.",
    choices=["I solved it, continue", "Skip this page"]
)

# For Cloudflare / anti-bot pages:
clarify(
    question="Cloudflare/bot-detection is blocking [URL]. The visible browser window should show the challenge. Please solve it there, then reply 'done'."
)
```

### Step 4 — Resume after user intervention

After the user confirms via `clarify`, call `browser_snapshot` again to get the current page state (which should now be the post-login or post-CAPTCHA page). Continue your automation normally.

If the current URL is still the same auth page, check again — the user may be mid-flow. Ask for confirmation again or try a different approach.

### Step 5 — Clean up

When done browsing, close the browser session:

```python
# Close the browser session (the visible window stays open — it's the user's)
# This just tells Hermes to disconnect from CDP
browser_navigate(url="about:blank", task_id="browse_session")  # clear page
```

The visible Chrome window stays open so the user can continue using it normally.

## Using browser_vision for CAPTCHA detection

When `browser_snapshot` text is ambiguous, use `browser_vision` to take a screenshot and inspect it visually for CAPTCHA elements, login forms, or auth walls:

```python
vision_result = browser_vision(task_id="browse_session", question="Is this page showing a CAPTCHA challenge, a login form, or any authentication wall? Describe what you see.")
```

This is especially useful for:
- Cloudflare challenge pages (often have minimal text)
- Visual CAPTCHAs (image-based challenges)
- Custom login UIs that use images/icons rather than text labels
- OAuth consent screens

## Handling Anti-Bot Detection

Some sites detect automation and block headless browsers. The visible CDP-connected Chrome is a **real browser** with a real user profile, which avoids most anti-bot detection. If a site still blocks you:

1. **Clear site data** in the visible browser (cookies, cache) and try again
2. **Use a different user profile** — create a fresh Chrome profile
3. **Try a different browser** — if using Chrome, try Edge or Brave (both support CDP on port 9222)
4. **Residential proxies** — if using Browserbase cloud mode, enable `BROWSERBASE_PROXIES=true`

## Summary of Tools Used

| Tool | Purpose |
|------|---------|
| `browser_navigate` | Navigate to a URL in the CDP-connected visible browser |
| `browser_snapshot` | Get the current page's accessibility tree (text representation) |
| `browser_vision` | Take a screenshot and analyze it visually for auth/CAPTCHA detection |
| `browser_click` | Click elements (safe to use on non-auth pages) |
| `browser_type` | Type text into fields (safe to use on non-auth pages) |
| `clarify` | Ask the user for help with login/CAPTCHA/auth walls |

## Headless Fallback (No Browser Available)

When no Chromium-based browser is installed and CDP mode isn't possible, the agent can fall back to **curl-based web requests through a SOCKS5 proxy**. This is useful for quick data lookups, but won't render JavaScript or bypass Cloudflare.

### Setup

```bash
# Use the SOCKS5 proxy for all requests
curl -sL --socks5-hostname 127.0.0.1:10808 <url> \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

### Search Engines That Work Through SOCKS5

| Engine | URL Pattern | Notes |
|--------|-------------|-------|
| **DuckDuckGo HTML** | `https://html.duckduckgo.com/html?q=<query>` | Returns clean HTML results; works through SOCKS5 proxy |
| **Bing** | `https://www.bing.com/search?q=<query>&setlang=en-US` | Works without proxy; may serve different locale |
| **Google** | `https://www.google.com/search?q=<query>&hl=en` | Usually blocked from SOCKS5 proxy IPs |

### Known Limitations (Distributor Sites)

These sites block programmatic access with Cloudflare and cannot be scraped via curl, even through a SOCKS5 proxy:

- `graybar.com` (Cloudflare)
- `anixter.com` / `wesco.com`
- `digikey.com`
- `mouser.com`
- `newark.com` / `element14.com`
- `testequity.com`

These require a real browser (CDP mode) to bypass. For data guarded behind these, use `clarify` to ask the user to either:
1. Install a browser for CDP mode, or
2. Manually look up the data and paste it in

### Sites That Work Headlessly

Some sites serve content without blocking:

- `corning.com` ecatalog (SAP Hybris) — product specs and part numbers available
- `fs.com` — product listings (may serve localized content)
- `cablesandkits.com`
- Raw API endpoints and public JSON feeds

## Pitfalls

### Chromium download geo-blocked

Google's `chrome-for-testing` CDN (`storage.googleapis.com`) and Playwright's CDN (`cdn.playwright.dev`) return **403 Access Denied** from certain geographic regions. Symptoms:

- `agent-browser install` → `Download failed: server returned HTTP 403`
- `npx playwright install chromium` → `Error: Access denied. This service is not available in your location`

**Fix:** Install a desktop browser manually (Chrome, Edge, or Brave) via the normal installer. That is a different download path and is not geo-blocked.

### SOCKS5 proxy not supported by Node.js tools

Node.js CLI tools (agent-browser, Playwright) use `undici`/`http` modules for downloads. These do not respect `ALL_PROXY=socks5://...` — they expect HTTP/S proxies. The `--socks5-hostname` flag only works with curl.

**Fix:** Set `HTTP_PROXY`/`HTTPS_PROXY` to an HTTP proxy, not SOCKS5, for Node.js tools. Or use curl for the data and pipe it to Python for processing.

### Cloudflare bot detection

Many e-commerce and distributor sites use Cloudflare. A headless curl request hits a challenge page immediately. Even a CDP-connected visible browser can trigger Cloudflare if the IP is flagged. Walking through the user's normal browser (not the agent's) is the most reliable bypass.

## Do NOT

- ❌ Try to fill in the user's credentials via `browser_type` — login fields are a security boundary
- ❌ Attempt to solve CAPTCHAs programmatically — this violates ToS and will likely fail
- ❌ Close the browser window the user is interacting with
- ❌ Navigate away from the page while the user is mid-login
- ❌ Store or log user credentials seen in URL parameters or page content
