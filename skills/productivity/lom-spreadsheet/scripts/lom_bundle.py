#!/usr/bin/env python3
"""
LOM Consolidator + Bundler — produces one workbook per input file,
with Mohaimen styling and smart item bundling.

BUNDLING RULES (1-2 per section, except مکانیک):
  POWER:  cables → "کابل‌های افشان مسی سایزهای مختلف"
          earthing → "سیستم ارت و صاعقه‌گیر"
  FAS:    push buttons → "شستی‌های تخلیه و توقف تخلیه"
          fire panels → "مراکز اعلام حریق تک لوپ آدرس پذیر"
  FES:    whole system → "سیستم کامل اطفای گازی FM200" (merged-cell sheets)
  CCTV:   cameras → "دوربین‌های HIKVISION BULLET و DOME"
  PASSIVE: OS2 fiber A+B → "فیبر نوری OS2 اوتردور 12Core مسیر A و B"
           ODF-EXT A+B → "ODF خارجی A و B ترمینیشن کامل"
  عمران:  structural metal → "سازه‌های فلزی و ورق‌های گالوانیزه"

Usage:
  python lom_bundle.py "path/to/LOM -DG.xlsx" [--output path] [--order ORDER]
"""

import sys, os, re
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

# ── Style constants ──

THIN = Side(style='thin')
THIN_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

TITLE_FONT    = Font(name='Calibri', size=20, bold=True)
HEADER_FONT   = Font(name='Calibri', size=12, bold=True)
SECTION_FONT  = Font(name='Calibri', size=22, bold=True)
DATA_FONT     = Font(name='Calibri', size=18, bold=False)
CENTER_WRAP   = Alignment(horizontal='center', vertical='center', wrap_text=True)
TEMPLATE_FILL = PatternFill(start_color='FF0070C0', end_color='FF0070C0', fill_type='solid')

COL_HEADERS   = ['ردیف', 'تجهیزات', 'توضیحات', 'مقدار', 'واحد', 'برند']

COL_WIDTHS = {
    'A': 8.6640625, 'B': 112.0,       'C': 41.6640625, 'D': 12.5546875,
    'E': 14.33203125, 'F': 22.33203125,
    'G': 9.109375, 'H': 13.0, 'I': 13.0, 'J': 13.0,
    'K': 13.0, 'L': 13.0, 'M': 13.0, 'N': 13.0,
}

SECTION_NAMES = {
    'civil': 'بخش عمران', 'mech': 'بخش مکانیک', 'mechanical': 'بخش مکانیک',
    'power': 'بخش POWER',
    'acs': 'بخش اکسس کنترل',
    'cctv': 'بخش CCTV',
    'passive': 'بخش PASSIVE',
    'fas': 'بخش FAS', 'firefighting': 'بخش FAS',
    'fes': 'بخش FES',
}

DEFAULT_ORDER = ['MECH', 'CIVIL', 'POWER', 'ACS', 'CCTV', 'PASSIVE', 'FAS', 'FES']

# ── Bundle matchers ──

def _match_any(text, *keywords):
    t = (text or '').lower()
    return any(k.lower() in t for k in keywords)

def _is_cable(item_b):
    return _match_any(item_b, 'cable', 'کابل') and not _match_any(item_b, 'back to back', 'کانکتور', 'سینی')

def _is_earthing(item_b):
    return _match_any(item_b, 'صاعقه', 'تسمه مسی', 'شینه ارت')

def _is_fas_pushbtn(item_b):
    return _match_any(item_b, 'شستی تخلیه', 'شستی توقف')

def _is_fas_panel(item_b):
    return _match_any(item_b, 'مرکز اعلام حریق')

def _is_cctv_camera(item_b):
    return _match_any(item_b, 'bullet', 'dome') and _match_any(item_b, 'camera')

def _is_os2_fiber(item_b):
    return _match_any(item_b, 'os2 outdoor')

def _is_odf_ext(item_b):
    return _match_any(item_b, 'odf-ext')

def _is_structural(item_b):
    return _match_any(item_b, 'پروفیل', 'ریل زیر رک', 'ورق گالوانیزه آجدار')

# ── Bundle definitions ──
# Each bundle: (section_key, items_matcher_fn, new_item_name, qty, unit, brand)
# Brand is auto-collected from matched items (not hardcoded).

BUNDLES = {
    'power': [
        {
            'match': lambda it: _is_cable(it.get('item', '')),
            'name': 'کابل‌های افشان مسی سایزهای مختلف مطابق RFP',
            'qty': 1, 'unit': 'مجموعه', 'brand': None,
            'desc': '',
        },
        {
            'match': lambda it: _is_earthing(it.get('item', '')),
            'name': 'سیستم ارت و صاعقه‌گیر شامل میله صاعقه‌گیر، تسمه مسی 3×25، شینه‌های ارت اولیه و ثانویه',
            'qty': 1, 'unit': 'مجموعه', 'brand': None,
            'desc': '',
        },
    ],
    'fas': [
        {
            'match': lambda it: _is_fas_pushbtn(it.get('item', '')),
            'name': 'شستی‌های تخلیه و توقف تخلیه',
            'qty': 1, 'unit': 'عدد', 'brand': None,
            'desc': '',
        },
        {
            'match': lambda it: _is_fas_panel(it.get('item', '')),
            'name': 'مراکز اعلام حریق تک لوپ آدرس پذیر (معمولی و دارای قابلیت اطفا)',
            'qty': 1, 'unit': 'عدد', 'brand': None,
            'desc': '',
        },
    ],
    'fes': [
        {
            'match': lambda it: True,  # FES uses merged cells — bundle the whole system
            'name': 'سیستم کامل اطفای گازی FM200 شامل سیلندر، گاز، شیر، فعال‌ساز، مانومتر، نازل، براکت و لوله‌کشی کلیه متعلقات',
            'qty': 1, 'unit': 'مجموعه', 'brand': None,
            'desc': '',
        },
    ],
    'cctv': [
        {
            'match': lambda it: _is_cctv_camera(it.get('item', '')),
            'name': 'دوربین‌های مداربسته HIKVISION شامل BULLET و DOME',
            'qty': 1, 'unit': 'مجموعه', 'brand': None,
            'desc': '',
        },
    ],
    'passive': [
        {
            'match': lambda it: _is_os2_fiber(it.get('item', '')),
            'name': 'Datwyler – فیبر نوری OS2 اوتردور 12Core مسیر A و B (۲ درام)',
            'qty': 1, 'unit': 'مجموعه', 'brand': None,
            'desc': '',
        },
        {
            'match': lambda it: _is_odf_ext(it.get('item', '')),
            'name': 'Datwyler - ODF خارجی A و B، ترمینیشن کامل ۱۲Core LC/UPC (۲ عدد)',
            'qty': 1, 'unit': 'مجموعه', 'brand': None,
            'desc': '',
        },
    ],
    'civil': [
        {
            'match': lambda it: _is_structural(it.get('item', '')),
            'name': 'سازه‌های فلزی و ورق‌های گالوانیزه کانتینر (پروفیل شاسی، ریل زیر رک، ورق کف)',
            'qty': 1, 'unit': 'مجموعه', 'brand': None,
            'desc': '',
        },
    ],
}

# ── Helpers ──

def derive_section_name(sheet_name):
    stem = re.sub(r'[-_\s]*(LOM|LOS)\s*$', '', sheet_name.strip(), flags=re.I).strip()
    key = stem.lower().replace('-', '').replace(' ', '').replace('_', '')
    return SECTION_NAMES.get(key, f'بخش {stem}')

def _cell(ws, row, col, value, font, alignment, border=THIN_BORDER):
    c = ws.cell(row=row, column=col, value=value)
    c.font = font; c.alignment = alignment; c.border = border
    return c

def _read_sheet_data(src, sheet_name):
    ws = src[sheet_name]
    items = []
    for r in ws.iter_rows(min_row=3, values_only=True):
        if any(v is not None for v in r):
            items.append({
                'item': str(r[1] or '').strip(),
                'desc': str(r[2] or '').strip(),
                'qty': r[3],
                'unit': str(r[4] or '').strip(),
                'brand': str(r[5] or '').strip(),
            })
    return items

def get_section_key(sheet_name):
    stem = re.sub(r'[-_\s]*(LOM|LOS)\s*$', '', sheet_name.strip(), flags=re.I).strip()
    return stem.lower().replace('-', '').replace(' ', '').replace('_', '')

def apply_bundles(items, section_key):
    """Apply bundle rules to items. Returns new list with bundled items."""
    rules = BUNDLES.get(section_key, [])
    if not rules:
        return items
    
    consumed = set()
    bundle_results = []
    
    for rule in rules:
        matched = [i for i, it in enumerate(items) if rule['match'](it)]
        if len(matched) >= 2:
            consumed.update(matched)
            # Collect brands from actual matched items
            brands = set()
            for idx in matched:
                if items[idx]['brand']:
                    brands.add(items[idx]['brand'])
            brand_str = ', '.join(sorted(brands)) if brands else ''
            
            bundle_results.append({
                'item': rule['name'],
                'desc': rule.get('desc', ''),
                'qty': rule['qty'],
                'unit': rule['unit'],
                'brand': brand_str,
                '_bundled': True,
            })
    
    # Build result keeping non-consumed items in original order,
    # inserting bundle results at the position of their first consumed item
    result = []
    inserted_bundles = set()
    
    for i, it in enumerate(items):
        if i in consumed:
            # Check if this is the first consumed item for any bundle
            for br in bundle_results:
                if br['item'] not in inserted_bundles:
                    rule_idx = next(
                        (ri for ri, rule in enumerate(rules)
                         if rule['name'] == br['item'] and rule['match'](it)),
                        None
                    )
                    if rule_idx is not None:
                        result.append(br)
                        inserted_bundles.add(br['item'])
        else:
            result.append(it)
    
    return result


# ── Main transform ──

def process_file(input_path, output_path, section_order=None):
    """Process one LOM file → consolidated + bundled Mohaimen-style workbook."""
    
    src = load_workbook(input_path)
    dst = Workbook()
    ws = dst.active
    
    stem = os.path.splitext(os.path.basename(input_path))[0]
    ws.title = re.sub(r'[-\s]+', '_', stem)[:31]
    
    for letter, w in COL_WIDTHS.items():
        ws.column_dimensions[letter].width = w
    
    all_sheets = src.sheetnames
    if section_order:
        ordered = []
        for item in section_order:
            item = item.strip()
            ordered.extend(s for s in all_sheets if item.lower() in s.lower())
        seen = set(ordered)
        ordered.extend(s for s in all_sheets if s not in seen)
    else:
        ordered = list(all_sheets)
    
    row = 1
    
    # Title
    title = src[ordered[0]].cell(row=1, column=1).value or 'لیست تجهیزات'
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)
    _cell(ws, 1, 1, title, TITLE_FONT, CENTER_WRAP)
    for c in range(2, 15):
        _cell(ws, 1, c, None, TITLE_FONT, CENTER_WRAP)
    for c in range(7, 15):
        ws.cell(row=1, column=c).fill = TEMPLATE_FILL
    row += 1
    
    # Headers
    for i, h in enumerate(COL_HEADERS, 1):
        _cell(ws, row, i, h, HEADER_FONT, CENTER_WRAP)
    for c in range(7, 15):
        _cell(ws, row, c, None, HEADER_FONT, CENTER_WRAP)
    row += 1
    
    total_original = 0
    total_bundled = 0
    
    for sname in ordered:
        items = _read_sheet_data(src, sname)
        if not items:
            continue
        
        section_key = get_section_key(sname)
        section_name = derive_section_name(sname)
        
        total_original += len(items)
        
        # Special handling for FES: merged-cell structure → one system item
        if section_key == 'fes':
            bundled_items = [{
                'item': 'سیستم کامل اطفای گازی FM200 شامل سیلندر، گاز، شیر، فعال‌ساز، مانومتر، نازل، براکت و لوله‌کشی کلیه متعلقات',
                'desc': '', 'qty': 1, 'unit': 'مجموعه', 'brand': '',
            }]
        else:
            bundled_items = apply_bundles(items, section_key)
        total_bundled += len(bundled_items)
        
        # Section header
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        _cell(ws, row, 1, section_name, SECTION_FONT, CENTER_WRAP)
        for c in range(2, 15):
            _cell(ws, row, c, None, SECTION_FONT, CENTER_WRAP)
        section_start = row + 1
        row += 1
        
        for it in bundled_items:
            vals = [None, it.get('item', ''), it.get('desc', ''),
                    it.get('qty'), it.get('unit', ''), it.get('brand', '')]
            for i, v in enumerate(vals, 1):
                _cell(ws, row, i, v, DATA_FONT, CENTER_WRAP)
            for c in range(7, 15):
                _cell(ws, row, c, None, DATA_FONT, CENTER_WRAP)
            row += 1
        
        for r in range(section_start, row):
            ws.row_dimensions[r].outline_level = 1
    
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = 9
    ws.print_area = f"'{ws.title}'!$A$1:$F${row - 1}"
    
    dst.save(output_path)
    src.close()
    dst.close()
    
    savings = total_original - total_bundled
    return output_path, total_original, total_bundled, savings


# ── CLI ──

if __name__ == '__main__':
    if len(sys.argv) < 2 or '--help' in sys.argv:
        print(__doc__)
        sys.exit(1)
    
    files = []
    custom_order = None
    
    args = sys.argv[1:]
    while args:
        arg = args.pop(0)
        if arg == '--output' and args:
            output = args.pop(0)
        elif arg == '--order' and args:
            custom_order = [x.strip() for x in args.pop(0).split(',')]
        else:
            files.append(arg)
    
    for fpath in files:
        if not os.path.exists(fpath):
            print(f"⚠️  Skipping (not found): {fpath}")
            continue
        
        stem = os.path.splitext(os.path.basename(fpath))[0]
        out_dir = os.path.dirname(fpath) or '.'
        out_path = os.path.join(out_dir, f'{stem}-Mohaimen.xlsx')
        
        result, orig, bundled, saved = process_file(fpath, out_path, custom_order)
        print(f"✅ {os.path.basename(fpath)}: {orig} items → {bundled} items (saved {saved})")
        print(f"   📁 {result}")
