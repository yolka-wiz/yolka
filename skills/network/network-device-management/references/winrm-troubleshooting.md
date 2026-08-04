# WinRM Remote Management Troubleshooting

Common issues when managing Windows machines via WinRM (pywinrm).

## Path Encoding Bug (`_x` → `_x005F_`)

### Symptom

`Add-AppxPackage -Register` or other path-sensitive PowerShell commands fail with:
```
Cannot find path 'C:\Program Files\...\ScreenSketch_11.2307.52.0_x005F_x64__8wekyb3d8bbwe\AppxManifest.xml'
```

Notice the `_x005F_` inserted where a literal `_x` appeared in the path (e.g. `_x64__` became `_x005F_x64__`).

### Root Cause

When pywinrm sends PowerShell commands via `session.run_ps()`, the command string is wrapped in XML. The `_x` byte sequence in file paths is interpreted as the start of a Unicode escape (`_xHHHH_`) and the underscore (U+005F) gets encoded as `_x005F_`.

### Workarounds

**Option A — Environment variable** (best for `Add-AppxPackage`):
```powershell
$env:PKG = "C:\Program Files\WindowsApps\Microsoft.ScreenSketch_11.2307.52.0_x64__8wekyb3d8bbwe"
Add-AppxPackage -Register "$env:PKG\AppxManifest.xml" -DisableDevelopmentMode
```

**Option B — Use cmd.exe** (`run_cmd` instead of `run_ps`):
```python
sess.run_cmd('powershell.exe -Command "Add-AppxPackage -Register ..."')
```
This bypasses the PowerShell XML serialization layer.

**Option C — Short 8.3 path** (when available):
```powershell
# Find 8.3 name
cmd /c dir /x "C:\Program Files\WindowsApps"
# Use the short name (e.g. MICROS~1\WINDOW~1\...)
```

## AppX Deployment NOT Completing in WinRM

### Symptom

After `Add-AppxPackage -Register` via WinRM:
- `Status` shows `Ok`
- But `PackageUserInformation` is **empty `{}`** — zero users
- Launching the app interactively fails with error `0x87E10BC6` (cannot create process for package)

### Root Cause

WinRM sessions are **non-interactive logon sessions**. The AppX deployment pipeline requires interactive user profile activation, which doesn't happen in WinRM. The package registers at the system level but is never deployed to the user profile.

### Fix

**Option A — Log out and log back in** (simplest — triggers profile deployment).

**Option B — Run via scheduled task with interactive logon:**
```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-Command Add-AppxPackage -Register 'C:\...\AppxManifest.xml' -DisableDevelopmentMode"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(30)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
Register-ScheduledTask -TaskName "FixAppX" -Action $action -Trigger $trigger -Principal $principal -Force
Start-ScheduledTask -TaskName "FixAppX"
```

### Diagnosis

```powershell
# Check if user deployment happened
Get-AppxPackage -Name <PackageName> | Select-Object Name, Status, PackageUserInformation

# Check event logs for activation errors
Get-WinEvent -LogName "Microsoft-Windows-AppModel-Runtime/Admin" -MaxEvents 20 | 
    Where-Object { $_.Id -eq 203 } | Format-Table TimeCreated, Message -Wrap
```

## Printer Driver Troubleshooting

WinRM is effective for diagnosing and fixing Windows printer issues when the physical printer is connected via USB or network.

### Diagnosis Flow

1. **Check printer status:**
   ```powershell
   Get-CimInstance Win32_Printer -Filter "Name = 'Printer Name'" |
       Select-Object PrinterStatus, DetectedErrorState, PrinterState, WorkOffline
   # PrinterStatus: 3=Idle, 4=Printing/Unknown
   # DetectedErrorState: 0=NoError, 2=Error
   # PrinterState: 0=Idle, 1024=IO_ACTIVE (stuck job)
   ```

2. **Check print queue for stuck jobs:**
   ```powershell
   Get-PrintJob -PrinterName "Printer Name" -ErrorAction SilentlyContinue |
       Select-Object Id, DocumentName, JobStatus, JobSize, TimeSubmitted
   # "Printing, Retained" status = job stuck in spooler
   ```

3. **Check PrintService admin event logs (critical):**
   ```powershell
   Get-WinEvent -LogName "Microsoft-Windows-PrintService/Admin" -MaxEvents 50 |
       Select-Object TimeCreated, Id, LevelDisplayName, Message | Format-Table -Wrap
   ```
   
   **Common error codes:**
   | Event ID | Error | Meaning |
   |----------|-------|---------|
   | 365 | Error 126: Module not found | Print processor DLL missing or failed to load |
   | 365 | Error 2: File not found | Driver file missing from `spool\DRIVERS\x64\3\` |
   | 808 | Driver error | Driver version mismatch or corruption |
   | 372 | Printer not found | Port configuration issue |

4. **Check USB device connectivity:**
   ```powershell
   Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPClass -eq "Printer" }
   # ConfigManagerErrorCode: 0 = OK, 28 = driver not installed, 43 = hardware failure
   ```

### Fix: Missing Print Processor DLL (Error 126)

**Symptom:** Event 365 in PrintService/Admin: "Windows could not load print processor XxxPrintProc because EnumDatatypes failed. Error code 126. Module: XxxPrintProc.dll"

**Root cause:** The printer driver's companion print processor DLL (e.g. `HP2030PP.DLL`) is missing from the driver folder. The print processor converts RAW/XPS data to the printer's native page description language before sending to the port monitor.

**Fix steps:**

1. **Obtain the missing DLL** from the manufacturer's driver package
2. **Copy to the driver folder:**
   ```powershell
   Copy-Item "C:\Temp\HP2030PP.DLL" "C:\Windows\System32\spool\DRIVERS\x64\3\" -Force
   ```
3. **Also copy to the print processors folder:**
   ```powershell
   Copy-Item "C:\Temp\HP2030PP.DLL" "C:\Windows\System32\spool\prtprocs\x64\" -Force
   # Some drivers expect the file under a specific name (e.g. HP2030PrintProc.dll)
   Copy-Item "C:\Temp\HP2030PP.DLL" "C:\Windows\System32\spool\prtprocs\x64\HP2030PrintProc.dll" -Force
   ```
4. **Restart the spooler:**
   ```powershell
   Stop-Service Spooler -Force
   Remove-Item "C:\Windows\System32\spool\PRINTERS\*" -Force -ErrorAction SilentlyContinue
   Start-Service Spooler
   ```
5. **Verify:**
   ```powershell
   "Test page - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" |
       Out-Printer -Name "Printer Name"
   Get-PrintJob -PrinterName "Printer Name" -ErrorAction SilentlyContinue
   # Queue should be empty (job completed)
   ```

### Fix: Clear Stuck Print Jobs

When a job is stuck in "Printing, Retained" state, it blocks all subsequent jobs:

```powershell
# Method 1: Stop spooler, delete files, restart
Stop-Service Spooler -Force
Remove-Item "C:\Windows\System32\spool\PRINTERS\*" -Force -ErrorAction SilentlyContinue
Start-Service Spooler

# Method 2: Remove CIM instance (if print queue API fails)
$job = Get-CimInstance Win32_PrintJob -Filter "Name LIKE '%PrinterName%' AND JobId=5"
$job | Remove-CimInstance
```

## File Transfer Between Machines via HTTP (When SMB Fails)

When you need to transfer files to a remote machine via WinRM but SMB isn't available (different subnets, credential mismatch, firewall rules):

### Approach: Temporary HTTP Server

1. **On your machine** (the one with the files), start a Python HTTP server:
   ```bash
   python -m http.server 18080 --bind <your-ip-in-target-subnet> &
   ```
   
2. **On the remote machine** (via WinRM), download the needed files:
   ```powershell
   $wc = New-Object Net.WebClient
   $wc.DownloadFile("http://<your-ip>:18080/filename.dll", "C:\Windows\Temp\filename.dll")
   ```

3. **Verify:**
   ```powershell
   Get-Item "C:\Windows\Temp\filename.dll" | Select-Object Length, LastWriteTime
   ```

### Limitations

- Firewall must allow the port (choose an unblocked high port like 18080-18090)
- The machine must be reachable on the chosen network interface/IP
- HTTP only (no TLS) — acceptable for internal/CCTV segments
- Stop the server when done

### Alternative: Base64 Chunked Transfer

If HTTP isn't possible, encode files as base64 and transfer via WinRM commands. For files larger than ~10KB, split into chunks and reconstruct on the remote side:

```python
# Encode
import base64
b64 = base64.b64encode(data).decode('ascii')
chunks = [b64[i:i+15000] for i in range(0, len(b64), 15000)]

# On remote side - first chunk creates file, subsequent chunks append
powershell_cmd = "[System.IO.File]::WriteAllBytes(path, [System.Convert]::FromBase64String(chunk))"
```

## SnippingTool (ScreenSketch) Specific Known Issues

- The modern SnippingTool is packaged as `Microsoft.ScreenSketch`
- The `PackageUserInformation` not populating via WinRM is the most common cause of `0x87E10BC6`
- The executable moved in newer versions (11.2307.52.0+): `ScreenSketch.exe` → `SnippingTool\SnippingTool.exe`
- Entry point changed to `Windows.FullTrustApplication`
- The old (11.2201.12.0) version has `ScreenSketch.exe` at root level
- Having two versions on disk can cause confusion — provisioned packages are cleaned up on `Remove-AppxPackage -AllUsers`
