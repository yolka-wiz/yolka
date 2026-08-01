#!/usr/bin/env python3
"""
Batch LOM Consolidator — Process multiple LOM files into one workbook,
one Mohaimen-style sheet per file.

Usage:
  python batch_lom_consolidate.py --output "path/to/output.xlsx" [options] file1.xlsx file2.xlsx ...

Options:
  --output <path>       Output path (required)
  --order <order>       Comma-separated section order, e.g. "MECH,CIVIL,ACS,POWER,.."
  --sheet-names <list>  Comma-separated sheet names for each input file

Example:
  python batch_lom_consolidate.py --output "LOM-ALL.xlsx" \
    --order "MECH,CIVIL,ACS,POWER,FAS,FES,CCTV,PASSIVE" \
    --sheet-names "DG,NOC,IT02" \
    "LOM -DG.xlsx" "LOM-NOC.xlsx" "LOM -IT02.xlsx"
"""

import sys, os, re
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

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
    'power': 'بخش POWER', 'acs': 'بخش اکسس کنترل', 'cctv': 'بخش CCTV',
    'passive': 'بخش PASSIVE', 'fas': 'بخش FAS', 'firefighting': 'بخش FAS',
    'fes': 'بخش FES',
}

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
    return [list(r[:6]) for r in ws.iter_rows(min_row=3, values_only=True)
            if any(v is not None for v in r)]

def process_file_into_worksheet(src_path, ws, section_order=None):
    src = load_workbook(src_path)
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

    for letter, w in COL_WIDTHS.items():
        ws.column_dimensions[letter].width = w

    row = 1
    title = src[ordered[0]].cell(row=1, column=1).value or 'لیست تجهیزات'
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)
    _cell(ws, 1, 1, title, TITLE_FONT, CENTER_WRAP)
    for c in range(2, 15):
        _cell(ws, 1, c, None, TITLE_FONT, CENTER_WRAP)
    for c in range(7, 15):
        ws.cell(row=1, column=c).fill = TEMPLATE_FILL
    row += 1

    for i, h in enumerate(COL_HEADERS, 1):
        _cell(ws, row, i, h, HEADER_FONT, CENTER_WRAP)
    for c in range(7, 15):
        _cell(ws, row, c, None, HEADER_FONT, CENTER_WRAP)
    row += 1

    for sname in ordered:
        data = _read_sheet_data(src, sname)
        if not data:
            continue
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        _cell(ws, row, 1, derive_section_name(sname), SECTION_FONT, CENTER_WRAP)
        for c in range(2, 15):
            _cell(ws, row, c, None, SECTION_FONT, CENTER_WRAP)
        section_start = row + 1
        row += 1
        for d in data:
            padded = list(d) + [None] * (6 - len(d))
            for i, v in enumerate(padded, 1):
                _cell(ws, row, i, v, DATA_FONT, CENTER_WRAP)
            for c in range(7, 15):
                _cell(ws, row, c, None, DATA_FONT, CENTER_WRAP)
            row += 1
        for r in range(section_start, row):
            ws.row_dimensions[r].outline_level = 1

    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = 9
    ws.print_area = f"'{ws.title}'!$A$1:$F${row - 1}"

    src.close()
    return row - 1

def batch_consolidate(file_paths, output_path, section_order=None, sheet_names=None):
    dst = Workbook()
    default_ws = dst.active

    for i, fpath in enumerate(file_paths):
        if not os.path.exists(fpath):
            print(f"Skipping (not found): {fpath}")
            continue
        stem = os.path.splitext(os.path.basename(fpath))[0]
        sheet_name = re.sub(r'[-\s]+', '_', stem)[:31]
        if sheet_names and i < len(sheet_names):
            sheet_name = sheet_names[i][:31]
        ws = default_ws if i == 0 else dst.create_sheet(title=sheet_name)
        if i == 0:
            ws.title = sheet_name
        total_rows = process_file_into_worksheet(fpath, ws, section_order)
        print(f"  {os.path.basename(fpath)} -> '{ws.title}' ({total_rows} rows)")

    dst.save(output_path)
    dst.close()
    print(f"Saved -> {output_path}")

if __name__ == '__main__':
    if len(sys.argv) < 3 or '--help' in sys.argv:
        print(__doc__)
        sys.exit(1)
    output_path = None; file_args = []; sheet_names = []; custom_order = None
    args = sys.argv[1:]
    while args:
        arg = args.pop(0)
        if arg == '--output' and args:         output_path = args.pop(0)
        elif arg == '--order' and args:        custom_order = [x.strip() for x in args.pop(0).split(',')]
        elif arg == '--sheet-names' and args:  sheet_names = [x.strip() for x in args.pop(0).split(',')]
        else:                                  file_args.append(arg)
    if not output_path:
        output_path = os.path.join(os.path.dirname(file_args[0]) if file_args else '.', 'LOM-ALL-Mohaimen.xlsx')
    batch_consolidate(file_args, output_path, custom_order, sheet_names)
