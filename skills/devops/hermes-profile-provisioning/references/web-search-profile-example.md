# Web Search Profile — Full Provisioning Walkthrough

This reference documents every step of creating the `web-search` Hermes profile,
including all the pitfalls encountered and the fixes applied. Use as a template
when provisioning any specialized search/scraping profile.

## 1. Create Profile

```bash
hermes profile create web-search \
  --description "Web search, scraping and data extraction specialist. Uses Playwright, Camoufox, curl_cffi and scrapling for anti-bot circumvention." \
  --no-alias
```

Creates `~/.hermes/profiles/web-search/` with 69 bundled skills.

## 2. Write SOUL.md

Overwrite the default generic SOUL with a role-specific one covering:
- **Worldview**: fetch beats browse, progressive tooling, structured output
- **Expertise**: curl_cffi, Scrapling, Playwright, Camoufox, search engines
- **Personality**: efficient, methodical, resilient, human-aware
- **Tool escalation chain**: curl_cffi → Scrapling → Playwright → Camoufox → user cookies
- **Boundaries**: no programmatic CAPTCHA solving, rate limiting, robots.txt respect

## 3. Write config.yaml

Key settings:

```yaml
model:
  default: deepseek-v4-flash
  provider: opencode-go
  base_url: https://opencode.ai/zen/go/v1
  api_mode: chat_completions

web:
  backend: curl_cffi
  use_gateway: false

browser:
  headless: true
  default_timeout: 30000

platform_toolsets:
  cli:
    - browser
    - clarify
    - code_execution
    - delegation
    - file
    - memory
    - terminal
    - web
    # ... plus session_search, skills, todo, vision, cronjob
```

## 4. Workspace + venv

```bash
cd ~/.hermes/profiles/web-search/workspace
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel -q
```

## 5. Requirements

```
curl-cffi>=0.7.0
httpx>=0.27.0
httpx-socks>=0.7.0
requests>=2.31.0
pysocks>=1.7.1
beautifulsoup4>=4.12.0
lxml>=5.0.0
selectolax>=0.3.0
parsel>=1.8.0
scrapling>=0.4.0
playwright>=1.40.0
camoufox>=0.4.0
pandas>=2.0.0
orjson>=3.9.0
pyyaml>=6.0
```

Install: `source venv/bin/activate && pip install -r requirements.txt`

## 6. Geo-blocking Pitfall

Playwright's CDN (`cdn.playwright.dev`) returns 403 from some regions.
**Fix:** Install system Chromium instead:

```bash
sudo apt install -y chromium
```

Then use with:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path='/usr/bin/chromium',
        headless=True,
        args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
    )
```

Set these in `.env`:

```
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
```

## 7. .env

```
WORKSPACE_DIR=/home/agent/.hermes/profiles/web-search/workspace
VIRTUAL_ENV=/home/agent/.hermes/profiles/web-search/workspace/venv
PATH=...venv/bin:/usr/local/bin:/usr/bin:/bin
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
SOCKS5_PROXY=127.0.0.1:10808
WEB_SEARCH_TOOL=curl_cffi
```

Note: `read_file` cannot display `.env`. Use `terminal cat`.

## 8. Custom Skills Created

| Skill | Purpose |
|-------|---------|
| `web-search/tool-escalation` | 5-level escalation chain with code examples |
| `web-search/cookie-harvesting` | Detect blocking, ask user for cookies, load into tools |
| `web-search/search-execution` | Multi-engine search (DDG, Bing, Google) + caching + rate limiting |
| `software-development/human-in-the-loop-browser` | Copied from devops profile for CAPTCHA bypass |

## 9. Memory

Initial `MEMORY.md` covers: tool info, escalation chain, search engine URLs, cookie handling, proxy, rate limiting (15-20 req/min, 5-min cache).

## 10. Verification

```bash
hermes profile list       # shows web-search
hermes profile show web-search  # Profile: web-search, Skills: 73, .env: exists, SOUL.md: exists
```

Python import checks for all 10+ packages pass. Playwright fetches `https://example.com` successfully with system Chromium.

## Pitfalls Unique to This Profile

- **camoufox version**: `>=0.4.0` installs latest (0.5.4). Pin if stability needed.
- **scrapling deprecation**: `AsyncFetcher()` warns about deprecated logic in v0.4+. Use `AsyncFetcher.configure()` per docs.
- **curl-cffi request args**: Use `impersonate="chrome131"` for best TLS fingerprint mimicry. Available: `chrome99` through `chrome131`, `safari15_3` through `safari18_0`.
- **SOCKS5 + Node.js**: `ALL_PROXY=socks5://...` is not respected by Node.js tools. Use curl or Python for proxy routing.
