# Windows Printer Troubleshooting via WinRM

## HP LaserJet P2035 — Stuck Print Jobs (Real-World Example)

### Symptoms
- Printer shows in device list, prints queue shows jobs with status "Printing, Retained"
- No output ever comes out of the printer
- `Get-Printer` shows `PrinterStatus: Normal` but jobs never complete

### Root Cause
An Excel file job (`??? ?????1404(6).xlsx`) was stuck with "Printing, Retained" status, keeping the printer in `PrinterState=1024 (IO_ACTIVE)`. All subsequent jobs waited behind it.

### Fix Applied
```powershell
# 1. Stop spooler
Stop-Service Spooler -Force

# 2. Delete all spool files (SHD, SPL, TMP)
Remove-Item "C:\Windows\System32\spool\PRINTERS\*" -Force

# 3. Start spooler
Start-Service Spooler

# 4. Verify
Get-CimInstance Win32_Printer -Filter "Name = 'Hewlett-Packard HP LaserJet P2035'" |
    Select-Object PrinterStatus, DetectedErrorState, PrinterState, JobCount
```

### Before vs After

| Metric | Before | After |
|--------|--------|-------|
| PrinterStatus | 4 (Unknown) | 3 (Idle) |
| DetectedErrorState | 2 (Error) | 0 (NoError) |
| PrinterState | 1024 (IO_ACTIVE) | 0 (Idle) |
| JobCount | 1 | 0 |

## Driver Version Issue

The HP P2035 had TWO drivers installed:

| Driver | MajorVersion | Type |
|--------|-------------|------|
| HP LaserJet P2035 Class Driver | 4 | v4 Class Driver (minimal) |
| HP LaserJet P2035 | 3 | v3 Full Driver (recommended) |

The printer was using the v4 Class Driver, which lacks full PCL6 support for older printers. Fixed by switching:

```powershell
Set-Printer -Name "Hewlett-Packard HP LaserJet P2035" -DriverName "HP LaserJet P2035"
Restart-Service Spooler -Force
```

## Diagnostic Command Cheat Sheet

```powershell
# Quick health check
$p = Get-CimInstance Win32_Printer -Filter "Name = '<printer>'"
Write-Output "Status:$($p.PrinterStatus) Error:$($p.DetectedErrorState) State:$($p.PrinterState)"
Write-Output "Offline:$($p.WorkOffline) Jobs:$($p.JobCount)"

# Full queue inspection
Get-PrintJob -PrinterName "<printer>" | Select-Object Id, DocumentName, JobStatus, JobState

# Check printer port
Get-PrinterPort -Name USB001 | Format-List *

# Check USB device presence
Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match "P2035|LaserJet" }

# Print service events (last 30)
Get-WinEvent -FilterHashtable @{LogName="Microsoft-Windows-PrintService/Admin"} -MaxEvents 30
```
