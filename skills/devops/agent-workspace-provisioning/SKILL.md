---
name: agent-workspace-provisioning
description: "Provisions a Linux server as an agent workspace with tools for PDF, XLSX, DOCX, CSV, web browsing, network automation, and Persian/RTL support. Covers venv setup, system dependencies, geo-blocked CDN workarounds, and workspace documentation."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [workspace, provisioning, linux, dev-environment, python, tools]
    related_skills: [server-iac-provisioning, persian-rtl-documents]
---

# Agent Workspace Provisioning

Use this skill when the user wants to prepare a Linux (Debian/Ubuntu) server
as an agent workspace — installing tools for document processing, web automation,
network device interaction, and Persian/RTL support.

**Related skills:**
- `server-iac-provisioning` — desktop service debloating (CUPS, Avahi, Bluetooth, etc.)
- `persian-rtl-documents` — Persian OCR, fonts, bidi, and RTL PDF creation in detail

---

## Quick-Reference Checklist

- [ ] Assess existing state (Python, Node, disk)
- [ ] (Optional) Debloat unwanted desktop services
- [ ] Create workspace directory structure
- [ ] Generate Persian locale and install fonts
- [ ] Install system dependencies (Chromium, chromedriver, tesseract, jq)
- [ ] Create Python virtual environment
- [ ] Install tool stack by category
- [ ] Handle geo-blocked CDN downloads
- [ ] Create AGENTS.md documentation
- [ ] Verify each tool works end-to-end

---

## Step 1: Pre-flight Assessment

```bash
# Python version & pip
python3 --version && pip3 --version && which python3

# Node (if needed)
node --version 2>/dev/null

# Disk
df -h ~

# Existing home layout
du -sh ~/* 2>/dev/null | sort -rh | head -10

# Existing Python packages
pip3 list 2>/dev/null | head -20

# System packages of interest
dpkg -l | grep -iE 'libreoffice|poppler|chromium|tesseract|python3-venv'
```

**Minimum requirements:** Python 3.10+, ~5GB free disk, sudo access.

---

## Step 2 (Optional): Debloat Desktop Services

If the target was installed with a desktop environment (KDE Plasma, GNOME, etc.)
and needs cleanup:

> Load the `server-iac-provisioning` skill and follow its
> **"Post-Install Cleanup: Debloating a Desktop-Installed Debian Server"** section.
>
> Key steps: lock desktop metapackages with `apt-mark manual`, dry-run removals,
> stop/purge CUPS, Avahi, ModemManager, Bluetooth, fwupd, wpa_supplicant, etc.

Always **ask the user first** what desktop components to keep (SDDM, krdp, etc.)
before removing anything.

---

## Step 3: Workspace Directory Layout

```bash
mkdir -p ~/workspace/{pdf,xlsx,docx,csv,network,web,scripts,samples}
```

Results in:
```
~/workspace/
├── pdf/              # PDF working directory
├── xlsx/             # Spreadsheet working directory
├── docx/             # Word document working directory
├── csv/              # CSV working directory
├── network/          # Network automation configs & scripts
├── web/              # Web scraping output / screenshots
├── scripts/          # Custom helper scripts
└── samples/          # Sample / test files
```

---

## Step 4: Persian / RTL Support

```bash
# Generate Persian locale
sudo sed -i 's/^# fa_IR.UTF-8/fa_IR.UTF-8 UTF-8/' /etc/locale.gen
sudo locale-gen

# Install Persian fonts
sudo apt install -y fonts-farsiweb fonts-noto-arabic

# Install Persian OCR
sudo apt install -y tesseract-ocr tesseract-ocr-fas

# Verify
locale -a | grep fa_IR
fc-list :lang=fa | head -5
```

For detailed Persian OCR and RTL PDF creation, see the `persian-rtl-documents` skill.

---

## Step 5: System Dependencies

```bash
sudo apt update -qq
sudo apt install -y \
  chromium \
  chromium-driver \
  jq \
  tesseract-ocr \
  libreoffice \
  python3-venv \
  git \
  curl \
  poppler-utils
```

| Package | Purpose |
|---------|---------|
| `chromium` + `chromium-driver` | Headless browser (Selenium/Playwright) |
| `jq` | JSON CLI processing |
| `tesseract-ocr` | OCR engine |
| `libreoffice` | docx↔pdf, xlsx↔csv format conversion (headless) |
| `python3-venv` | Python virtual environment |
| `poppler-utils` | `pdftotext`, `pdfinfo`, `pdftoppm` |

---

## Step 6: Python Virtual Environment

```bash
cd ~/workspace
python3 -m venv agent-env
source agent-env/bin/activate
pip install --upgrade pip setuptools wheel -q
```

---

## Step 7: Install Tool Stack

All tools install cleanly into the venv. Install by category:

### PDF Tools
```bash
pip install pymupdf pikepdf pdfminer.six reportlab
```

| Tool | Purpose |
|------|---------|
| **pymupdf** (fitz) | Read/write PDFs, text extraction, annotations |
| **pikepdf** | Low-level PDF structure, metadata, encryption |
| **pdfminer.six** | Advanced text extraction, layout analysis |
| **reportlab** | Generate PDFs from scratch (charts, tables) |

### Spreadsheet & Document Tools
```bash
pip install openpyxl xlsxwriter pandas python-docx csvkit
```

| Tool | Purpose |
|------|---------|
| **openpyxl** | Read/write .xlsx (styles, formulas, charts) |
| **xlsxwriter** | Write .xlsx with advanced formatting |
| **pandas** | DataFrame → xlsx/csv/json, data analysis |
| **python-docx** | Read/write .docx |
| **csvkit** | `csvstat`, `csvcut`, `csvgrep` (system command) |

### Web Automation
```bash
pip install selenium beautifulsoup4 lxml requests playwright
```

| Tool | Purpose |
|------|---------|
| **Selenium** | Full browser automation (clicks, JS, screenshots) |
| **BeautifulSoup4** | HTML parsing and extraction |
| **requests** | HTTP client |
| **Playwright** | Alternative browser automation |

### Network Automation
```bash
pip install netmiko paramiko nornir napalm scrapli pyyaml jinja2
```

| Tool | Purpose |
|------|---------|
| **netmiko** | Multi-vendor SSH (Cisco, Juniper, Arista) |
| **paramiko** | Low-level SSH client |
| **nornir** | Parallel network automation framework |
| **napalm** | Unified config management |
| **scrapli** | Fast network device SSH |
| **PyYAML + Jinja2** | Config file parsing & templating |

### Persian / RTL
```bash
pip install arabic-reshaper python-bidi
```

| Tool | Purpose |
|------|---------|
| **arabic-reshaper** | Reshape Arabic-script letters for rendering |
| **python-bidi** | Bidirectional text algorithm |

---

## Step 8: Geo-Blocked CDN Workarounds

When the server's geographic region blocks CDN downloads (Playwright browser
binaries, ChromeDriver, etc.), bypass via system packages:

### Playwright → System Chromium

Playwright's CDN (`cdn.playwright.dev`) geo-blocks some regions. Use the
system-installed Chromium with `executable_path` instead:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path='/usr/bin/chromium',
        args=['--no-sandbox', '--disable-dev-shm-usage']
    )
    page = browser.new_page()
    page.goto('https://example.com')
    print(page.title())
    browser.close()
```

Do NOT run `playwright install` — it will fail with "Access denied" / 403.
The system Chromium is already installed at `/usr/bin/chromium`.

### Selenium → System Chromedriver

Selenium Manager also tries to download chromedriver from Google's CDN and
fails with 403/Forbidden. Install `chromium-driver` via apt:

```bash
sudo apt install chromium-driver
```

This installs chromedriver matching the system Chromium version to
`/usr/bin/chromedriver`. Selenium discovers it automatically:

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

opts = Options()
opts.binary_location = '/usr/bin/chromium'
opts.add_argument('--headless')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=opts)
driver.get('https://example.com')
print(driver.title)  # "Example Domain"
driver.quit()
```

---

## Step 9: Create AGENTS.md

Write an AGENTS.md at `~/workspace/AGENTS.md` covering:

1. **Environment info**: OS version, hostname, user, sudo access
2. **Activation**: `source ~/workspace/agent-env/bin/activate`
3. **Directory layout**: what each subdirectory is for
4. **Tool table by category**: purpose and import statement
5. **Quick-reference code snippets**: Selenium, netmiko, Persian PDF, LibreOffice conversion
6. **Verification confirmation**: what was tested and passed

Template structure:

```markdown
# AGENTS.md — Agent Workspace on <hostname>

## Overview
<OS>, SSH user `<user>` with NOPASSWD sudo.

## Activation
source ~/workspace/agent-env/bin/activate

## Directory Layout
...

## Tools by Category
| Category | Tools |
|----------|-------|
| PDF | pymupdf, pikepdf, ... |
| XLSX | openpyxl, pandas, ... |
| ... | ... |

## Quick Code Examples
...

## Geo-Blocking Notes
<if applicable>
```

---

## Step 10: Verification

```python
import sys

# PDF
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((50,50), 'Hello PDF Agent!')
doc.save('/tmp/test_agent.pdf')
print('pymupdf OK:', doc.page_count, 'pages')

# XLSX
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active; ws['A1'] = 'Test'; wb.save('/tmp/test_agent.xlsx')
print('openpyxl OK')

# DOCX
import docx
d = docx.Document(); d.add_paragraph('Test'); d.save('/tmp/test_agent.docx')
print('python-docx OK')

# CSV
import pandas as pd
pd.DataFrame({'col': ['test']}).to_csv('/tmp/test_agent.csv', index=False)
print('pandas CSV OK')

# Network
import netmiko, paramiko, nornir, napalm, scrapli
print('netmiko, paramiko, nornir, napalm, scrapli OK')

# Web
import requests
print('requests OK:', requests.get('https://example.com').status_code)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
opts = Options()
opts.binary_location = '/usr/bin/chromium'
opts.add_argument('--headless'); opts.add_argument('--no-sandbox')
d = webdriver.Chrome(options=opts)
d.get('https://example.com'); print('selenium OK:', d.title); d.quit()

# Persian
import arabic_reshaper, bidi.algorithm
print('arabic-reshaper + bidi OK')

# LibreOffice conversion (shell)
# libreoffice --headless --convert-to pdf sample.docx --outdir /tmp/

print('ALL VERIFIED')
```

Also verify:
```bash
# Listening ports — only expected ones (SSH, maybe krdp/kdeconnectd)
ss -tlnp

# Running services — no cruft
systemctl list-units --type=service --state=running

# Disk used after cleanup
df -h /
```

---

## Pitfalls

- **apt-mark before purge on KDE desktops**: `kde-plasma-desktop` metapackages mark `plasma-desktop` and `plasma-workspace` as auto-installed. If you purge packages that break the metapackage's dep chain (e.g. `udisks2`, `upower`), apt removes the entire desktop. Fix: `sudo apt-mark manual plasma-desktop plasma-workspace sddm` before purging. See `server-iac-provisioning` skill for the full debloat table.
- **Playwright `playwright install` fails with 403**: The CDN is geo-blocked for some regions. Use system Chromium with `executable_path='/usr/bin/chromium'` instead. Do NOT attempt to download from the CDN.
- **Selenium Manager fails with 403/Forbidden**: Same geo-blocking. Install `chromium-driver` via apt; Selenium discovers it automatically. Do NOT rely on Selenium Manager downloads.
- **LibreOffice `--headless` may warn about Java**: `Warning: failed to launch javaldx` is harmless. Conversion still works.
- **Persian locale fails with "Bad entry"**: The line in `/etc/locale.gen` must be `fa_IR.UTF-8 UTF-8` with no trailing whitespace. A trailing space after `UTF-8` causes `locale-gen` to parse it as `'fa_IR.UTF-8 '` (trailing space in the charset field) which it rejects.
- **Persian text in shell heredocs**: Passing Persian characters via `cat << 'EOF' ... EOF` in bash can cause SyntaxErrors in Python. Use explicit Unicode escapes (`\uXXXX`) or write the Python script to a file with `write_file` first, then execute it.
- **`fontname` parameter ignored when `fontfile=` is passed**: pymupdf loads the font from the file path; the `fontname` string is for internal reference only and has no effect on rendering.
- **Don't skip AGENTS.md**: Without documentation, the next agent (or human) landing on the server has no idea what's installed or how to activate it. Always create the file.
