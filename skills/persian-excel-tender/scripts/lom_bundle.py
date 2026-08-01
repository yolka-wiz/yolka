#!/usr/bin/env python3
"""
LOM Consolidator + Bundler — one workbook per input file,
Mohaimen styling + smart item bundling.

Usage: python lom_bundle.py "file1.xlsx" "file2.xlsx" [--order ORDER]
"""
import sys, os, re
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
THIN=Side(style='thin'); TB=Border(left=THIN,right=THIN,top=THIN,bottom=THIN)
TF=Font(name='Calibri',size=20,bold=True); HF=Font(name='Calibri',size=12,bold=True)
SF=Font(name='Calibri',size=22,bold=True); DF=Font(name='Calibri',size=18,bold=False)
CW=Alignment(horizontal='center',vertical='center',wrap_text=True)
TPL=PatternFill(start_color='FF0070C0',end_color='FF0070C0',fill_type='solid')
CH=['ردیف','تجهیزات','توضیحات','مقدار','واحد','برند']
CWd={'A':8.6640625,'B':112.0,'C':41.6640625,'D':12.5546875,'E':14.33203125,'F':22.33203125,
     'G':9.109375,'H':13.0,'I':13.0,'J':13.0,'K':13.0,'L':13.0,'M':13.0,'N':13.0}
SN={'civil':'بخش عمران','mech':'بخش مکانیک','mechanical':'بخش مکانیک','power':'بخش POWER',
    'acs':'بخش اکسس کنترل','cctv':'بخش CCTV','passive':'بخش PASSIVE','fas':'بخش FAS',
    'firefighting':'بخش FAS','fes':'بخش FES'}
def _mc(t,*k): t=(t or '').lower(); return any(x.lower() in t for x in k)
BUNDLES={
 'power':[
  {'match':lambda it:_mc(it.get('item',''),'cable','کابل') and not _mc(it.get('item',''),'back to back','کانکتور','سینی'),
   'name':'کابل‌های افشان مسی سایزهای مختلف مطابق RFP','qty':1,'unit':'مجموعه','brand':None},
  {'match':lambda it:_mc(it.get('item',''),'صاعقه','تسمه مسی','شینه ارت'),
   'name':'سیستم ارت و صاعقه‌گیر شامل میله صاعقه‌گیر، تسمه مسی 3×25، شینه‌های ارت','qty':1,'unit':'مجموعه','brand':None}],
 'fas':[
  {'match':lambda it:_mc(it.get('item',''),'شستی تخلیه','شستی توقف'),
   'name':'شستی‌های تخلیه و توقف تخلیه','qty':1,'unit':'عدد','brand':None},
  {'match':lambda it:_mc(it.get('item',''),'مرکز اعلام حریق'),
   'name':'مراکز اعلام حریق تک لوپ آدرس پذیر (معمولی و دارای قابلیت اطفا)','qty':1,'unit':'عدد','brand':None}],
 'cctv':[{'match':lambda it:_mc(it.get('item',''),'bullet','dome') and _mc(it.get('item',''),'camera'),
          'name':'دوربین‌های مداربسته HIKVISION شامل BULLET و DOME','qty':1,'unit':'مجموعه','brand':None}],
 'passive':[
  {'match':lambda it:_mc(it.get('item',''),'os2 outdoor'),
   'name':'Datwyler – فیبر نوری OS2 اوتردور 12Core مسیر A و B (۲ درام)','qty':1,'unit':'مجموعه','brand':None},
  {'match':lambda it:_mc(it.get('item',''),'odf-ext'),
   'name':'Datwyler - ODF خارجی A و B، ترمینیشن کامل ۱۲Core LC/UPC (۲ عدد)','qty':1,'unit':'مجموعه','brand':None}],
 'civil':[{'match':lambda it:_mc(it.get('item',''),'پروفیل','ریل زیر رک','ورق گالوانیزه آجدار'),
           'name':'سازه‌های فلزی و ورق‌های گالوانیزه کانتینر (پروفیل شاسی، ریل زیر رک، ورق کف)','qty':1,'unit':'مجموعه','brand':None}],
}
def dsn(s):
    stem=re.sub(r'[-_\s]*(LOM|LOS)\s*$','',s.strip(),flags=re.I).strip()
    return SN.get(stem.lower().replace('-','').replace(' ','').replace('_',''),f'بخش {stem}')
def gsk(s):
    stem=re.sub(r'[-_\s]*(LOM|LOS)\s*$','',s.strip(),flags=re.I).strip()
    return stem.lower().replace('-','').replace(' ','').replace('_','')
def cl(w,r,c,v,f,a,b=TB):
    x=w.cell(row=r,column=c,value=v); x.font=f; x.alignment=a; x.border=b; return x
def rd(src,sh):
    w=src[sh]
    return [{'item':str(r[1] or '').strip(),'desc':str(r[2] or '').strip(),'qty':r[3],
             'unit':str(r[4] or '').strip(),'brand':str(r[5] or '').strip()}
            for r in w.iter_rows(min_row=3,values_only=True) if any(v is not None for v in r)]
def ab(items,sk):
    rs=BUNDLES.get(sk,[]); 
    if not rs: return items
    cd=set(); br=[]
    for rule in rs:
        m=[i for i,it in enumerate(items) if rule['match'](it)]
        if len(m)>=2:
            cd.update(m); bs=set()
            for idx in m:
                if items[idx]['brand']: bs.add(items[idx]['brand'])
            br.append({'item':rule['name'],'desc':'','qty':rule['qty'],'unit':rule['unit'],
                       'brand':', '.join(sorted(bs)),'_bundled':True})
    res=[items[i] for i in range(len(items)) if i not in cd]
    for b in br:
        if b not in res:
            for rule in rs:
                if rule['name']==b['item']:
                    m=[i for i,it in enumerate(items) if rule['match'](it)]
                    if m: res.insert(sum(1 for j in range(m[0]) if j not in cd),b)
                    break
    return res
def pf(ip,op,so=None):
    src=load_workbook(ip); dst=Workbook(); ws=dst.active
    stem=os.path.splitext(os.path.basename(ip))[0]
    ws.title=re.sub(r'[-\s]+','_',stem)[:31]
    for l,w in CWd.items(): ws.column_dimensions[l].width=w
    shs=src.sheetnames
    if so:
        ordd=[]
        for item in so:
            item=item.strip(); ordd.extend(s for s in shs if item.lower() in s.lower())
        seen=set(ordd); ordd.extend(s for s in shs if s not in seen)
    else: ordd=list(shs)
    row=1
    t=src[ordd[0]].cell(row=1,column=1).value or 'لیست تجهیزات'
    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=6)
    cl(ws,1,1,t,TF,CW)
    for c in range(2,15): cl(ws,1,c,None,TF,CW)
    for c in range(7,15): ws.cell(row=1,column=c).fill=TPL
    row+=1
    for i,h in enumerate(CH,1): cl(ws,row,i,h,HF,CW)
    for c in range(7,15): cl(ws,row,c,None,HF,CW)
    row+=1; to=0; tb=0
    for s in ordd:
        its=rd(src,s)
        if not its: continue
        sk=gsk(s); sn=dsn(s); to+=len(its)
        if sk=='fes':
            bundled=[{'item':'سیستم کامل اطفای گازی FM200 شامل سیلندر، گاز، شیر، فعال‌ساز، مانومتر، نازل، براکت و لوله‌کشی','desc':'','qty':1,'unit':'مجموعه','brand':''}]
        else: bundled=ab(its,sk)
        tb+=len(bundled)
        ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=6)
        cl(ws,row,1,sn,SF,CW)
        for c in range(2,15): cl(ws,row,c,None,SF,CW)
        ss=row+1; row+=1
        for it in bundled:
            vs=[None,it.get('item',''),it.get('desc',''),it.get('qty'),it.get('unit',''),it.get('brand','')]
            for i,v in enumerate(vs,1): cl(ws,row,i,v,DF,CW)
            for c in range(7,15): cl(ws,row,c,None,DF,CW)
            row+=1
        for r in range(ss,row): ws.row_dimensions[r].outline_level=1
    ws.page_setup.orientation='landscape'; ws.page_setup.paperSize=9
    ws.print_area=f"'{ws.title}'!$A$1:$F${row-1}"
    dst.save(ip); src.close(); dst.close()
    return op,to,tb,to-tb
if __name__=='__main__':
    if len(sys.argv)<2 or '--help' in sys.argv: print(__doc__); sys.exit(1)
    fls=[]; co=None; args=sys.argv[1:]
    while args:
        a=args.pop(0)
        if a=='--order' and args: co=[x.strip() for x in args.pop(0).split(',')]
        else: fls.append(a)
    for f in fls:
        if not os.path.exists(f): print(f'⚠️  Skip: {f}'); continue
        stem=os.path.splitext(os.path.basename(f))[0]
        out=os.path.join(os.path.dirname(f) or '.',f'{stem}-Mohaimen.xlsx')
        _,o,b,s=pf(f,out,co)
        print(f'✅ {os.path.basename(f)}: {o} → {b} items (-{s})')
