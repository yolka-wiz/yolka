---
name: windows-software-install
description: Install software on remote Windows machines via WinRM — silent installs, firewall rules, Defender handling, and activation patchers.
---

# Windows Software Installation via WinRM

## When to use

Installing MSI/EXE software packages on remote Windows machines where you have WinRM (port 5985) credentials. Works for:
- Silent/automated installers (MSI, InnoSetup, NSIS)
- GUI installers that need to be staged for the interactive user
- Pre-activation cracks/patchers
- Firewall blocking for offline apps

## Prerequisites

- `pywinrm` installed (comes with Hermes Agent venv)
- WinRM enabled on target (port 5985)
- NTLM auth credentials (admin-level user)

## Workflow

### 1. Connect and check state

```python
import winrm

host = "TARGET_IP"
s = winrm.Session(host, auth=("USER", "PASS"), transport='ntlm')

def run_ps(cmd):
    r = s.run_ps(cmd)
    out = r.std_out.decode('utf-8', errors='replace').strip()
    err = r.std_err.decode('utf-8', errors='replace').strip()
    return out, err, r.status_code
```

### 2. Copy installer from network share

```powershell
# Setup PSDrive with share credentials
$pass = ConvertTo-SecureString "SHARE_PASS" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("SHARE_USER", $pass)
New-PSDrive -Name S -PSProvider FileSystem -Root "\\SERVER\Share" -Credential $cred | Out-Null

# Copy installer locally (C:\Windows\Temp auto-clears on reboot)
Copy-Item "S:\installer.exe" "C:\Windows\Temp\installer.exe" -Force
```

### 3. Handle Windows Defender

**Disable real-time protection** (before cracked/PUA software):

```powershell
Set-MpPreference -DisableRealtimeMonitoring $true
Add-MpPreference -ExclusionPath "C:\Windows\Temp"
```

**Re-enable after installation** (optional):

```powershell
Set-MpPreference -DisableRealtimeMonitoring $false
```

### 4. Install silently via SYSTEM scheduled task

GUI installers hang over WinRM. Always run via `schtasks` as SYSTEM:

```powershell
# Create task
schtasks /Create /SC ONCE /TN "InstallApp" /TR "C:\Windows\Temp\installer.exe /S" /ST 00:00 /RL HIGHEST /RU SYSTEM /F

# Run it
schtasks /Run /TN "InstallApp"

# Wait, then check result
schtasks /Query /TN "InstallApp" /V /FO LIST
# Look for "Last Result" — 0 = success
```

**Common silent switches:**

| Installer Type | Switch | Examples |
|---|---|---|
| MSI | `/qn /norestart` | `msiexec /i "app.msi" /qn /norestart` |
| InnoSetup | `/S` or `/VERYSILENT /SUPPRESSMSGBOXES` | WinRAR, many apps |
| NSIS | `/S` | Various |
| Wise | `/s` | |
| InstallShield | `-s -f1"setup.iss"` | |
| AnyDesk | `--install "C:\Program Files\AnyDesk" --start-with-win --silent` | |
| Adobe Setup | via `msiexec /i "AcroPro.msi" TRANSFORMS="AcroPro.mst" /qn` | |

### 5. Stage GUI-only installers/patchers for user

Cracks, activators, and GUI patchers can't run over WinRM. Copy to the user's Desktop:

```powershell
Copy-Item "C:\Windows\Temp\crack.exe" "C:\Users\USERNAME\Desktop\crack.exe" -Force
```

### 6. Block executables in Windows Firewall

```powershell
# Block all EXEs in a folder from outbound internet
$folder = "C:\Program Files\SomeApp"
$excludeList = @("uninstall","Unin","VC_redist","dotNetFx")
Get-ChildItem $folder -Filter "*.exe" | ForEach-Object {
    $skip = $false
    foreach ($ex in $excludeList) { if ($_.Name -match $ex) { $skip = $true } }
    if (-not $skip) {
        $ruleName = "Block_" + $_.BaseName
        netsh advfirewall firewall add rule name=$ruleName dir=out program=$($_.FullName) action=block
    }
}
```

### 7. Verify installation

```powershell
# Registry check
Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" |
    Where-Object { $_.DisplayName -match "APP_NAME" }

# File check
Test-Path "C:\Program Files\SomeApp\main.exe"

# Version check
(Get-Item "C:\Program Files\SomeApp\main.exe").VersionInfo.FileVersion
```

### 8. Cleanup

```powershell
schtasks /Delete /TN "InstallApp" /F
Remove-Item "C:\Windows\Temp\installer.exe" -Force
Remove-Item "C:\Windows\Temp\setup_files" -Recurse -Force
```

## Common pitfalls

- **ISO drive letters disappear** between PowerShell sessions — mount ISO + copy files in a single `run_ps()` call
- **MSI CAB files** must all be present in the same directory, or install fails with Error 1311
- **m0nkrus/MPT cracks are GUI-only** — cannot run via WinRM. Copy to Desktop for the user
- **Defender flags PUA/cracks** — disable real-time monitoring before staging cracked software
- **schtasks /ST earlier than current time** is just a warning, the task still runs
- **4GB RAM VMs can OOM** during large ISO copies + msiexec — watch for WinRM disconnects
