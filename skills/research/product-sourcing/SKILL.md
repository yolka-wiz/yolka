---
name: product-sourcing
description: "Research pricing and find vendors for hardware/specialty products. Scrape known vendor pricelists, web-search for prices across providers, collect international provider contact info, and save structured results."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, pricing, procurement, vendor-sourcing, web-scraping]
---

# Product Sourcing Research

Research pricing and find vendors for hardware/specialty products. Typically involves:
1. Reading a product list from Excel/CSV
2. Scraping known vendor pricelists for matches
3. Web-searching for prices in chunks
4. Collecting provider contact info and international shipping details
5. Saving structured results to CSV/Excel

## Workflow

### Step 1: Read the product list
```python
import openpyxl, os
wb = openpyxl.load_workbook(os.path.expanduser('~/Desktop/filename.xlsx'))
ws = wb.active
# Print headers and sample rows to understand the data shape
```

### Step 2: Scrape known vendor pricelists
Use `curl` with proxy (if needed) + regex extraction. This is the most reliable method for structured HTML tables:
```bash
curl -s --proxy socks5h://127.0.0.1:10808 --max-time 30 "URL" | \
  grep -oP 'class="partNum">\K[^<]+'
```

Or in Python for multi-page scraping:
```python
import requests, re, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
session = requests.Session()
session.verify = False
session.proxies = {'http': 'socks5h://127.0.0.1:10808', 'https': 'socks5h://127.0.0.1:10808'}
session.headers.update({'User-Agent': 'Mozilla/5.0 ...'})
```

**Key pitfall:** Install `pysocks` before using SOCKS proxy with Python requests:
```bash
pip install pysocks
```

### Step 3: Match products against scraped data
Exact part-number matching first, then fall back to fuzzy/description matching if no exact matches.

### Step 3b: Build price predictions from similar products
When exact matches are scarce but similar products exist (same class, different length/type), build a linear price model from the priced items:

```python
# 1. Collect all products of the same category from the price list
# 2. Group by quantifiable attribute (length, fiber count, port count)
from collections import defaultdict
groups = defaultdict(list)
for length_ft, price in trunk_data:
    groups[length_ft].append(price)

# 3. Take median price per distinct length (handles duplicate entries)
lengths, prices = [], []
for l in sorted(groups.keys()):
    med = sorted(groups[l])[len(groups[l]) // 2]
    lengths.append(l)
    prices.append(med)

# 4. Simple linear regression: price = intercept + slope * attribute
n = len(lengths)
sum_x, sum_y = sum(lengths), sum(prices)
sum_xy = sum(x * y for x, y in zip(lengths, prices))
sum_xx = sum(x * x for x in lengths)
slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
intercept = (sum_y - slope * sum_x) / n
```

**Corning EDGE part number length extraction patterns:**
- Trunk cables: suffix `U{length}M` — `Z757512QLZ55U010M` = 10m
- Patch cords: `[A-Z]{3}{length}M` — `E797902QNZ200{01.5}M` = 1.5m, `E787802GNZ160{02}M` = 2m
- Cat6A patch: `A{3-digit-length}-` — `A020` = 2m, `A030` = 3m

**Unit conversion for US distributor models:** Trunk cable prices from US distributors are in feet.
```python
def predict_trunk_price(length_m, model):
    length_ft = length_m * 3.28084
    return model['intercept'] + model['slope'] * length_ft
```

**Example models built from AmeriResponse Corning data:**
| Product | Model | Source data points |
|---|---|---|
| 12-fiber OM4 EDGE trunk | $531.24 + $3.41/ft | 3 lengths (50-100ft) |
| 12-fiber OM3 EDGE trunk | $537.66 + $2.77/ft | 19 lengths (20-200ft) |
| 12-fiber OS2 EDGE trunk | $622.02 + $0.87/ft | 9 lengths (30-150ft) |
| OM4 EDGE patch cord | ~$62.66 base + ~$1.0/additional m | Edge jumper series |
| OS2 EDGE patch cord | ~$42.00 base + ~$1.5/additional m | Estimated from SM jumpers |

**Pitfall:** Convert meters to feet before applying US distributor pricing models. Always note the source currency and unit in your output.

### Step 4: Web search for remaining products in chunks
Use `delegate_task` to search in parallel batches of 5 products:
```python
# Split products into chunks of 5
chunks = [products[i:i+5] for i in range(0, len(products), 5)]
```

### Step 5: Collect provider contact info
For each provider found, collect:
- Company name
- Website URL
- Email / Phone / Fax
- International shipping capability
- Notes (e.g., "site accessible but products require login", "403 on automated access")

### Step 6: Save results
- Update the original Excel with prices and supplier links
- Create `providers.csv` with provider contact details

## Pitfalls

### Enterprise/B2B products are hard to find online
Specialized products (e.g., Corning EDGE data center infrastructure) are often:
- Sold through authorized distributors only (not public retail)
- Quote-based pricing (no listed prices)
- Not indexed by standard search engines
- Distributors may carry a SUBSET of products from a product line — check carefully before concluding

**Strategy:** Check if the product line is enterprise/B2B vs consumer/retail before investing heavily in web searching. If enterprise, prioritize direct manufacturer contact or authorized distributor lists. Even when a distributor's catalog seems unrelated (e.g., AmeriResponse is fiber-cable focused), they may still carry some EDGE chassis, modules, and trunk cables — search for prefix patterns (e.g., `EDGE`, `ECM`, `G7575`, `G9090`) in their full pricelist.

### Many vendor sites block automated access
Major distributors (Graybar, WESCO, Anixter, Amazon, eBay) frequently return 403/503 to automated requests. Even with proxy and proper User-Agent headers.

**Workarounds:**
- Try the proxy at `socks5h://127.0.0.1:10808`
- Use `-k` (insecure) flag with curl for SSL issues
- Try alternative search engines (Yandex, Startpage) when Google/Bing block
- Some sites work with `requests` but not `curl` or vice versa

### /tmp path discrepancy on Windows (MSYS)
Files saved to `/tmp/file.jpg` via bash/curl exist at `/tmp/file.jpg` in bash but at `C:\Users\<user>\AppData\Local\Temp\file.jpg` in Python. Use `cygpath -w` to resolve:
```bash
cygpath -w /tmp/file.jpg
```

### AmeriResponse pricelist structure
AmeriResponse Corning pricelist has 3 pages. Part numbers are in `class="partNum"`, prices in `class="price"`. Their catalog is primarily fiber cable (part numbers like `001E313113124`), but they DO carry some Pretium EDGE products — chassis (`EDGE01USP`), modules (`ECMUM120593Q`), and EDGE trunk cables (`G757512...`, `G909012...`). Always search for multiple prefix patterns (e.g., `EDGE`, `ECM`, `G75`, `G90`, `CCH`) across all pages.

### Search in chunks, not all at once
The user explicitly asked for chunks of 5 to avoid overwhelming searches. This also helps track progress and handle failures gracefully.

## Provider Discovery Checklist
When building a provider list, check:
- [ ] Does the site ship internationally?
- [ ] Can I actually access the site (not blocked)?
- [ ] Do they carry the specific product line?
- [ ] Is pricing public or quote-only?
- [ ] Contact info (email, phone, address)?
