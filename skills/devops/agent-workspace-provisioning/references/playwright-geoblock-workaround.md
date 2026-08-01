# Playwright Geo-Block Workaround

When Playwright's CDN (cdn.playwright.dev) returns 403 from your region:

## The Problem

```
Error: Download failed: server returned code 403
Details: We're sorry, but this service is not available in your location
```

This typically happens in Iran and other sanctioned regions.

## The Fix — Use System Chromium

Install the system Chromium package instead of Playwright's bundled browser:

```bash
sudo apt install -y chromium chromium-driver
```

Playwright's Python API works fine with the system browser if you pass `executable_path`:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path='/usr/bin/chromium',
        args=['--no-sandbox']
    )
    page = browser.new_page()
    page.goto('https://example.com')
    print(page.title())
    browser.close()
```

## Alternative — Selenium (More Reliable)

For JS-heavy page automation, Selenium with system chromedriver is the more reliable option:

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

opts = Options()
opts.binary_location = '/usr/bin/chromium'
opts.add_argument('--headless')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=opts)
try:
    driver.get('https://example.com')
    print(driver.title)
finally:
    driver.quit()
```

## Verdict

Both Playwright (with system executable) and Selenium work. Selenium + system chromedriver is preferred because:
1. No download step needed — everything from apt
2. Version matching guaranteed (chromium + chromium-driver from same apt source)
3. Works in geo-blocked regions without workarounds

Playwright is useful when you need its unique features (network interception, multi-browser context, etc.) — just pass `executable_path` and skip the bundled browser download.
