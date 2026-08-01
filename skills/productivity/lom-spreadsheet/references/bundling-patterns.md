# LOM Item Bundling Patterns

Captured from analysis of LOM-Mohaimen.xlsx reference file (Jul 2026).
Use these patterns when asked to simplify or bundle line items.

## User's Explicit Guidance (captured Jul 2026)

> "dont summarize to much, maybe one or two items bundled at most in every
>  section, you can split some items as well, and bundle items related to
>  each other like different size of cables as a pack of cables, but for
>  the ones with the same count"

This means:
- **Max 1-2 bundles per section** — conservative approach
- **Bundle adjacent items** that share context (same brand, same category)
- **Same-qty items** are the best bundle candidates
- **Cable packs** (different sizes, same supplier) are always good
- **Splitting** is also acceptable if an item is too broad
- **Skip مکانیک section** unless user explicitly asks

## General Rules

- At most 1-2 bundles per section
- Bundle adjacent items that share: same brand, same category, same unit
- Same-qty items are strongest candidates (matching quantities)
- Cable packs: different cable sizes from same supplier → bundle as
  "کابل‌های افشان مسی سایزهای مختلف" (qty=۱ مجموعه)
- A/B redundant pairs: duplicate items for Path A / Path B → combine
  with "(A و B)" notation
- Skip the مکانیک section unless explicitly asked
- Structural metal items with brand `-` and qty=۱ مجموعه → bundle

## FES Special Handling

FES-LOM sheets use a **7-column layout** (brand in column G, not F)
with merged cells B3:B11 and E3:E11. The standard 6-column reader
produces garbled data. **Always handle FES as a special case:**

- Do NOT attempt to read individual component rows
- Emit a single bundled item: "سیستم کامل اطفای گازی FM200 شامل
  سیلندر، گاز، شیر، فعال‌ساز، مانومتر، نازل، براکت و لوله‌کشی"
- qty=۱ مجموعه, brand collected from source if available

## Brand Collection

Bundle brands must be **collected from the actual matched items' data**,
never hardcoded in rules. If matched items have different brands, join
them with ", ". This correctly handles source files where (e.g.) FAS
items all use FIKE instead of the expected HONEYWELL.

## Per-Section Bundle Reference

### POWER (31 items → ~8 after bundles)

**Bundle 1 — Cables pack** (all CABLE items, same brand):
- 14 different CABLE items, all same brand (سیمیا/سیم پود/افشار نژاد), unit=مترطول
- → "کابل‌های افشان مسی سایزهای مختلف مطابق RFP" — qty=۱ مجموعه

**Bundle 2 — Earthing system** (items 7-10):
- میله صاعقه‌گیر, تسمه مسی 3×25, شینه ارت اولیه, شینه ارت ثانویه
- Mixed qtys (4, 90m, 2, 4), but all earthing-related
- → "سیستم ارت و صاعقه‌گیر شامل میله صاعقه‌گیر، تسمه مسی 3×25، شینه‌های ارت اولیه و ثانویه"
- qty=۱ مجموعه

### FAS — اعلام حریق (12 items)

**Bundle 1** (items 1-2):
- شستی تخلیه + شستی توقف تخلیه (push buttons, qty=1 each)
- → "شستی‌های تخلیه و توقف تخلیه" — qty=۱ عدد

**Bundle 2** (items 6-7):
- مرکز اعلام حریق تک لوپ + مرکز اعلام حریق با قابلیت اطفا
- → "مراکز اعلام حریق تک لوپ آدرس پذیر (معمولی و دارای قابلیت اطفا)" — qty=۱ عدد

### FES — اطفای گازی (10 items, merged-cell sheet)

**Bundle — whole system:**
- FES sheets have merged cells, not individual line items
- → "سیستم کامل اطفای گازی FM200 شامل سیلندر، گاز، شیر، فعال‌ساز، مانومتر، نازل، براکت و لوله‌کشی کلیه متعلقات"
- qty=۱ مجموعه

### CCTV — دوربین (6 items)

**Bundle** (items 3-4):
- BULLET CAMERA (2) + DOME CAMERA (4), both HIKVISION
- → "دوربین‌های مداربسته HIKVISION شامل BULLET و DOME" — qty=۱ مجموعه

### PASSIVE (14 items)

**Bundle 1** (items 4-5):
- Datwyler OS2 Outdoor Path A + Path B, qty=۱ درام each
- → "Datwyler – فیبر نوری OS2 اوتردور 12Core مسیر A و B (۲ درام)"

**Bundle 2** (items 6-7):
- ODF-EXT-A + ODF-EXT-B, qty=۱ each
- → "Datwyler - ODF خارجی A و B، ترمینیشن کامل ۱۲Core LC/UPC (۲ عدد)"

### عمران (7 items)

**Bundle** (items 2, 3, 6):
- پروفیل شاسی, ریل زیر رک, ورق گالوانیزه کف — all brand `-`, qty=۱ مجموعه
- → "سازه‌های فلزی و ورق‌های گالوانیزه کانتینر (پروفیل شاسی، ریل زیر رک، ورق کف)" — qty=۱ مجموعه
