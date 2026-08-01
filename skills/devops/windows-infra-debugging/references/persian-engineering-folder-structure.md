# Persian Engineering Firm — Project Folder Structure

## When to Use

Designing or restructuring a file server for an Iranian (Persian-speaking) engineering firm
that works on tenders (مناقصه), does AutoCAD/DWG drawings, and needs to solve the version-conflict
problem where multiple engineers copy base plans and then lose track of revisions.

## The Version Problem

```
Engineer A draws Base_Plan.dwg → B copies it → C copies it
A updates Base_Plan.dwg → B & C don't know → continue on stale versions
```

## Solution: XREF + Single Source of Truth

Every engineer **XREFs** (AutoCAD External Reference) to the base plan in `01_پلان‌مبنا\فعلی\`.
They do NOT copy the file. When the base is updated, all linked drawings reflect it automatically
on next open.

## Folder Structure Template

```
پروژه‌ها\
└── 1405_نام‌پروژه\                  ← Year + project name (Persian date)
    │
    ├── 01_پلان‌مبنا\                 ← SINGLE SOURCE OF TRUTH for base plans
    │   ├── فعلی\                     ← Live version — all XREFs point here
    │   │   └── Base_Plan.dwg
    │   └── قبلی\                     ← Old revisions (never delete)
    │       ├── 1404-12-01_پلان‌اولیه.dwg
    │       └── 1405-03-15_بازبینی.dwg
    │
    ├── 02_نقشه‌ها\                   ← Discipline-specific drawings
    │   ├── برق\
    │   ├── مکانیک\
    │   └── معماری\
    │
    ├── 03_اسناد\                     ← Technical documents
    │   ├── LOM\
    │   ├── LOS_LOP\
    │   ├── مشخصات‌فنی\
    │   └── محاسبات\
    │
    ├── 04_پروپوزال\                  ← Proposal & bid documents
    │
    ├── 05_مکاتبات\                   ← Correspondence
    │   ├── کارفرما\
    │   └── مشاور\
    │
    ├── 06_گزارش‌ها\                  ← Progress / site reports
    │
    └── 07_تحویل‌نهایی\               ← Final signed-off delivery
        └── 1405-04-27\
            ├── نقشه‌ها\
            ├── اسناد\
            └── ضمائم\
```

## Shared Reference Folders (global, at server root)

```
کاتالوگ‌ها\                           ← Product/vendor catalogues (read-only)
├── برق\
├── مکانیک\
└── عمومی\

قالب‌ها\                              ← Empty templates for new projects
├── LOM_قالب.xlsx
├── LOS_قالب.xlsx
├── LOP_قالب.xlsx
├── پروپوزال_قالب.docx
├── Drawing_Base.dwg
└── نامه_نگاری_قالب.docx

گزارش_تغییرات.xlsx                    ← Change log for all projects
| تاریخ | تغییر‌دهنده | شرح‌تغییر | فایل |
```

## Naming Conventions

- **Dates**: YYYY-MM-DD format (Gregorian) or YYYY-MM-DD (Persian/Shamsi). Pick one and be consistent.
- **Files**: `تاریخ_توضیح.پسوند` — no spaces, Persian descriptions
- **Folders**: `شماره_نام` — leading numbers enforce sort order
- **Never** use spaces in filenames shared over SMB

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Persian folder names | User-facing structure, users are Persian-speaking engineers who search by Persian project names |
| Numbered prefixes (01_, 02_) | Enforce a consistent sort order regardless of alphabet |
| `فعلی\` and `قبلی\` in base plans | Never delete old revisions — they're lightweight and serve as audit trail |
| Separate `تحویل‌نهایی\` | Clean separation between WIP and delivered; the `readonly` user should only see past/final docs |
| `LOM\` inside اسناد not root | LOM/LOS/LOP are project deliverables, not standalone reference |
| Central `کاتالوگ‌ها\` | Eliminates 4+ copies of the same catalogue files found in personal folders |

## Migration From a Flat Personal-Folder Structure

When migrating from a structure like:
```
D:\Borna Rad - Shair\
├── Fani\           ← 50+ folders: projects, software, personal
├── Mali\           ← financial spreadsheets, setup files
├── Bazarghani\     ← tenders, price sheets
└── ...
```

Steps:
1. **Sort**: Separate project files from software/personal/catalogues
2. **Move** software to `D:\Software\` (central share)
3. **Move** catalogues to `کاتالوگ‌ها\`
4. **Create** `پروژه‌ها\` folder with the template structure
5. **Migrate** each person's project folders into `پروژه‌ها\1405_نام\` following the numbered subfolder scheme
6. **Set up** XREFs from discipline drawings to `01_پلان‌مبنا\فعلی\`
7. **Archive** `تعویض\` — dump rest there, sort later
8. **Create** `readonly` user with Read access to everything for audit/management visibility

## Read-Only Audit User

Create a user who can browse all shares but not modify anything:
```powershell
# Create user
$pwd = ConvertTo-SecureString "password" -AsPlainText -Force
New-LocalUser -Name "readonly" -Password $pwd -PasswordNeverExpires

# Grant SMB share-level read
Get-SmbShare | Where-Object {$_.Name -notmatch '\$$'} |
    ForEach-Object { Grant-SmbShareAccess -Name $_.Name -AccountName "FILE-SRV\readonly" -AccessRight Read -Force }

# Grant NTFS read on share roots
icacls "D:\مسیر" /grant "readonly:(OI)(CI)(RX)" /Q
```
