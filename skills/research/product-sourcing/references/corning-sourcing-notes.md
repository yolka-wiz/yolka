# Corning Product Sourcing - Provider Notes (2026-06-30)

## Providers Found

### AmeriResponse
- **Website:** https://www.amerisponse.com
- **Corning Pricelist:** https://www.amerisponse.com/Corning/Corning-Pricelist.html (3 pages)
- **Phone:** 1 (888) 349-5065
- **Fax:** 1 (405) 491-0040
- **Email:** Sales@Amerisponse.com
- **International:** Yes — 15+ years export experience, CIF/EXW/account shipping options
- **Products:** Fiber cable products AND some Pretium EDGE data center infrastructure:
  - EDGE chassis (EDGE01U, EDGE02U, EDGE04U, EDGE01USP, EDGE02UFP, EDGE801U, etc.)
  - EDGE modules (ECMUM120593Q, ECMUM120489G, ECMUM120593T, ECMUM121889G, ECMUM249393Q)
  - EDGE trunk cables (G7575 series OM3/OM4, G9090 series OS2 SM)
  - EDGE panels (EDGECP2490, EDGECP24E3, EDGECP48E3, EDGECP72U3)
  - EDGE tap modules (ETM5BG, ETM5BQ, ETM7AQ, ETM7BG, ETM7BQ)
  - CCH enclosures and panels
  - Standard fiber cable (part numbers like `001E313113124`)
- **Scraping method:** `curl --proxy socks5h://127.0.0.1:10808` + regex extraction or local file processing (the page can be saved as HTML). Extract with:
  ```python
  import re
  rows = re.findall(
      r'<tr><td class="itemId">(\d+)</td><td class="manufactureName">Corning</td>'
      r'<td class="partNum">([^<]+)</td><td class="description">([^<]*)</td>'
      r'<td class="price">([^<]*)</td>',
      html_content
  )
  ```

### FIS (Fiber Instrument Sales)
- **Website:** https://www.fiberinstrumentsales.com
- **Address:** 161 Clear Road, Oriskany, NY 13424
- **Phone:** 1-800-500-0347 / +1 315-736-2206
- **International:** Yes (10 international mentions on site)
- **Note:** Search functionality returns 404; product catalog not easily searchable via URL

### FS.com (FiberStore)
- **Website:** https://www.fs.com
- **Email:** supplier@fs.com, tech@fs.com
- **International:** Yes (814 international mentions, ships worldwide)
- **Note:** Large catalog, but Corning EDGE specific products not found in search

## Sites That Blocked Access (403/503)
- Graybar.com — 403
- WESCO.com — 403
- Anixter.com — 403
- Amazon.com — 503
- eBay.com — 403
- RackSolutions.com — 403
- CableOrganizer.com — 400/404

## Scraping Patterns That Worked

### AmeriResponse multi-page scrape (Python)
```python
import subprocess, re
pages = [
    "https://www.amerisponse.com/Corning/Corning-Pricelist.html",
    "https://www.amerisponse.com/Corning/Corning-Pricelist-P2.html",
    "https://www.amerisponse.com/Corning/Corning-Pricelist-P3.html"
]
all_products = {}
for page_url in pages:
    result = subprocess.run(
        ["curl", "-s", "--proxy", "socks5h://127.0.0.1:10808", "--max-time", "30", page_url],
        capture_output=True, text=True, timeout=35
    )
    rows = re.findall(
        r'class="partNum">([^<]+)</td><td class="description">([^<]+)</td><td class="price">([^<]+)</td>',
        result.stdout
    )
    for part, desc, price in rows:
        all_products[part.strip()] = {"description": desc.strip(), "price": price.strip()}
```

### FIS contact extraction
```python
# From about-us page
emails = re.findall(r'[\w.-]+@[\w.-]+\.\w+', r.text)
phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', r.text)
addr_patterns = re.findall(r'\d+\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl)[^<]*', r.text)
```

## Found Pricing Data (Pretium EDGE products via AmeriResponse)

### EDGE Chassis
| Part Number | Description | AmeriResponse Price |
|---|---|---|
| EDGE01U | 1U Rack-Mt Enclosure 8 Module Capacity | $566.38 |
| EDGE01USP | 1U Rack-Mount Enclosure 12 Module Capacity | $566.38 |
| EDGE01UFP | 1U Rack-Mount Enclosure 6 Module Capacity, 96 Fibers | $327.39 |
| EDGE02U | 2U Rack-Mt Enclosure 24 Module Capacity | $822.26 |
| EDGE02UFP | 2U Edge FX Fixed Tray Housing, 16 Panels, 192 Fibers | $669.30 |
| EDGE04U | 4U Rack-Mount Enclosure 48 Module Capacity | $1,088.72 |
| EDGE801U | 1U Edge8 Housing, Up To 12 Modules/Panels | $594.70 |
| EDGE802U | 2U Edge8 Housing, Up To 36 Modules/Panels | $863.36 |
| EDGE804U | 4U Edge8 Housing, Up To 72 Modules/Panels | $1,143.16 |

### EDGE Modules
| Part Number | Description | AmeriResponse Price |
|---|---|---|
| ECMUM120593Q | 12-Fiber Pretium Edge Module LC Dup to Pinned MTP 50um OM4 | $507.94 |
| ECMUM120593T | 12-Fiber Pretium Edge Module LC Dup to Pinned MTP 50um OM3 | $462.46 |
| ECMUM120489G | 12-Fiber Pretium Edge Module LC Dup to Pinned MTP SM OS2 | $506.17 |
| ECMUM121889G | 12-Fiber Pretium Edge Module Shuttered LC APC-MTP APC SM OS2 | $737.37 |
| ECMUM249393Q | Edge AO 2x3 Conversion Module 24-F Pinned MTP to Pinned MTP OM4 | $1,095.65 |

### EDGE Trunk Cables — Price Models (12-fiber MTP-MTP, 1-pull grip)
**OM4 (Pretium 550):** $531.24 + $3.41/ft (3 data points: 50-100ft)
**OM3 (Pretium 300):** $537.66 + $2.77/ft (19 data points: 20-200ft)
**OS2 SM:** $622.02 + $0.87/ft (9 data points: 30-150ft)

Convert meters to feet before applying: `length_ft = length_m * 3.28084`

### EDGE Patch Cords
- **OM4 LC-LC (reverse polarity):** ~$62.66 for 1m, + ~$1.0/additional meter
- **OS2 LC-LC (reverse polarity):** ~$42.00 for 1m, + ~$1.5/additional meter
- Similar part: `797902QD120001M` = $62.66 (2-Fiber OM4 Low-Loss Jumper, 1M)
- Edge jumper series: `797902TD12000NM` = $61.35 + ~$1.0/m (OM3)

### CCH Enclosures (lower-cost alternative to EDGE)
| Part Number | Description | Price |
|---|---|---|
| CCH01U | 12/48-F Rack-Mt Enclosure 1U | $252.73 |
| CCH02U | 24/96-F Rack-Mt Enclosure 2U | $289.78 |
| CCH03U | 36/144-F Rack-Mt Enclosure 3U | $328.98 |
| CCH04U | 72/288-F Rack-Mt Enclosure 4U | $369.24 |
| PCH01U | 12/48-F Rack-Mt Enclosure 1U (Pretium CCH) | $292.40 |

### EDGE Panels
| Part Number | Description | Price |
|---|---|---|
| EDGECP2490 | 24-Fiber MTP Connector Panel, Black SM | $86.58 |
| EDGECP24E3 | 24-Fiber MTP Connector Panel, Aqua MM | $86.58 |
| EDGECP48E3 | Edge Panel, 4x 12-Fiber MTP, Aqua MM | $153.31 |
| EDGECP72U3 | Edge AO Panel 72-F MTP OM3/OM4 | $226.34 |

### Cable Management
| Part Number | Description | Price |
|---|---|---|
| CJP01U | Closet Jumper Storage Panel 1U | $76.79 |
| CJP02U | Closet Jumper Storage Panel 2U | $88.58 |
| CJP03U | Closet Jumper Storage Panel 3U | $95.40 |

### EDGE Tap Modules
| Part Number | Description | Price |
|---|---|---|
| ETM5BG | Tap Module OS2 SM 50/50 Split, 12-F LC | $4,354.94 |
| ETM5BQ | Tap Module OM4 MM 50/50 Split, 12-F LC | $4,705.24 |
| ETM7BG | Tap Module OS2 SM 70/30 Split, 12-F LC | $4,354.94 |
| ETM7BQ | Tap Module OM4 MM 70/30 Split, 12-F LC | $4,705.24 |
| ETM7AQ | Tap Module 70/30 Split, LC/LC Duplex Shutter | $1,495.43 |

## Part Number Parsing Patterns

### Trunk Cables
`Z757512QLZ55U003M` → split as: `Z7575` (family) `12` (fibers) `QLZ55` (fiber type/loss) `U003` (length code) `M` (meters unit)
The length is the digits between `U` and `M`: `003` = 3 meters.

Regex: `U(\d+)M$` extracts the length in meters.

### Patch Cords
`E797902QNZ20001.5M` → `[A-Z]{3}{length-digits}M`
Regex: `[A-Z](\d{3})([\d.]+)M$` — 3-digit code + length value before M.
- `20001.5` = code `200` + length `01.5` → 1.5m
- `20002` = code `200` + length `02` → 2m
- `16003` = code `160` + length `03` → 3m

### Cat6A Patch Cords
`CCAAGB-G2002-A020-C0` → `A{3-digit-length}` → `A020` = 2m, `A030` = 3m
Regex: `A(\d{3})-` — take last 2 digits as meters (020 → 2m, 030 → 3m).

## Discount Expectations
- AmeriResponse prices are **retail list prices**
- Authorized distributors (Wesco, Graybar) typically offer **40-60% off list** for project quantities
- The Corning EDGE Configurator shows inflated "list prices" — use actual distributor data for budgeting
