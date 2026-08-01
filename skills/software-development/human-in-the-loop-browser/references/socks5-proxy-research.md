# SOCKS5 Proxy Web Research Techniques

Techniques for searching the web via curl + SOCKS5 proxy when no browser is available.

## Basic SOCKS5 curl

```bash
curl -sL --socks5-hostname 127.0.0.1:10808 "<url>" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

## Search Engine URLs

| Engine | URL | Works with SOCKS5? |
|--------|-----|---------------------|
| DuckDuckGo HTML | `https://html.duckduckgo.com/html?q=<query>` | Yes |
| DuckDuckGo Lite | `https://lite.duckduckgo.com/lite/?q=<query>` | Usually blocked (CAPTCHA) |
| Bing | `https://www.bing.com/search?q=<query>&setlang=en-US` | Yes, no proxy needed |
| Google | `https://www.google.com/search?q=<query>&hl=en&gl=US` | Usually blocked from proxy IPs |
| Google Shopping | `https://www.google.com/search?tbm=shop&q=<query>` | Usually blocked |
| Startpage | `https://www.startpage.com/sp/search?query=<query>` | Varies |

## Parsing DuckDuckGo HTML Results

```python
import re, subprocess

def ddg_search(query):
    url = f"https://html.duckduckgo.com/html?q={query.replace(' ', '+')}"
    result = subprocess.run(
        ["curl", "-sL", "--socks5-hostname", "127.0.0.1:10808", url,
         "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"],
        capture_output=True, text=True, timeout=20
    )
    html = result.stdout
    urls = re.findall(r'class="result__url"[^>]*>([^<]+)', html)
    snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)', html)
    titles = re.findall(r'class="result__a"[^>]*>([^<]+)', html)
    return list(zip(titles, urls, snippets))
```

## Extracting Clean Text from HTML

```python
def extract_text(html):
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text
```

## Finding Prices in Text

```python
prices = re.findall(r'\$[0-9,]+\.?[0-9]{0,2}', text)
```

## Known Site Behaviors

| Site | Accessible via curl? | Notes |
|------|---------------------|-------|
| corning.com/ecatalog | Yes | SAP Hybris e-commerce, returns full product pages |
| fs.com | Yes | May serve localized content (locale-based) |
| graybar.com | No | Cloudflare blocks |
| anixter.com/wesco.com | No | Cloudflare blocks |
| digikey.com | No | Anti-bot blocks |
| mouser.com | No | Anti-bot blocks |
| newark.com | No | Access denied |
| amazon.com | Yes | But complex JS rendering needed for prices |
