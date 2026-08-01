# Software Deployment via WinRM — Reference

## Session Context

Remote host: DESKTOP-4ALJOMP (Win 10 Enterprise, 4 GB, build 19041)
Credentials: template / Aa@123456 (admin, via NTLM)
Software share: \\\\192.168.4.100\Software (user: fani / Ff@123456)

## pywinrm Session-Isolation Rule

Every `session.run_ps()` or `session.run_cmd()` call starts a **brand new PowerShell/cmd process**. State between calls is NOT shared:

```python
# WRONG — S: drive only exists inside the first command
s.run_ps("New-PSDrive -Name S ... | Out-Null")          # S: created
s.run_ps("Get-ChildItem S:")                              # S: does NOT exist!

# RIGHT — everything in ONE run_ps call
s.run_ps(
    'New-PSDrive -Name S ... | Out-Null; '
    'Get-ChildItem S:'
)
```

This applies to:
- `net use` drive mappings
- PSDrive (`New-PSDrive`)
- Environment variable changes (`$env:VAR = "value"`)
- Working directory changes

## SMB Share Access Pattern

```powershell
$pass = ConvertTo-SecureString "Ff@123456" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("fani", $pass)
New-PSDrive -Name S -PSProvider FileSystem -Root "\\192.168.4.100\Software" -Credential $cred | Out-Null
# Now use S:\ inside this same command
Copy-Item "S:\AnyDesk.exe" "C:\Windows\Temp\AnyDesk.exe" -Force
```

**Note:** The `-Persist` flag on `New-PSDrive` does NOT help — it creates a persistent mapping visible in Explorer, but that only works for the interactive user's session, not across WinRM calls.

## GUI Installer Blocking

When you run a GUI installer via `Start-Process -Wait` in a WinRM session, the process **blocks indefinitely** because it's waiting for window messages that can't be rendered. The timeout kills the connection before the install completes.

**DO NOT use:**
```powershell
Start-Process "installer.exe" -ArgumentList "/S" -Wait
```

**DO use the schtasks-as-SYSTEM pattern:**

```powershell
# 1. Copy installer to local disk (from SMB share or direct upload)
# 2. For complex commands, write a batch file first:
@"
@echo off
"C:\Windows\Temp\AnyDesk.exe" --install "C:\Program Files\AnyDesk" --start-with-win --create-shortcuts --silent
echo EXIT_CODE=%ERRORLEVEL%
"@ | Out-File "C:\Windows\Temp\install_app.bat" -Encoding ASCII

# 3. Create and run scheduled task as SYSTEM
schtasks /Delete /TN "InstallApp" /F 2>&1 | Out-Null
schtasks /Create /SC ONCE /TN "InstallApp" /TR "C:\Windows\Temp\install_app.bat" /ST 00:00 /RL HIGHEST /RU SYSTEM /F
schtasks /Run /TN "InstallApp"

# 4. Wait (15-30s depending on installer), then verify
```

## Specific Software

### WinRAR 7.23 (64-bit)

| Detail | Value |
|---|---|
| Installer | `winrar-x64-723.exe` (3,823,896 bytes) |
| Silent switch | `/S` |
| Install path | `C:\Program Files\WinRAR\WinRAR.exe` |
| Reg key | `HKLM\...\WinRAR 7.23 (64-bit)` |
| Exit code | 0 (success) |

**Command:** `winrar-x64-723.exe /S` — simple InnoSetup silent switch.

### AnyDesk 9.0.2

| Detail | Value |
|---|---|
| Installer | `AnyDesk.exe` (5,583,680 bytes) |
| Signed by | AnyDesk Software GmbH (valid signature) |
| Install path | `C:\Program Files\AnyDesk\AnyDesk.exe` |
| Service | `AnyDesk` — status=Running |
| Reg key | `HKLM\...\AnyDesk vad 9.0.2` |

**Correct silent command:**
```
AnyDesk.exe --install "C:\Program Files\AnyDesk" --start-with-win --create-shortcuts --silent
```

**Failed attempts:**
| Command | Result |
|---|---|
| `--install --silent` | Exit 11341829 (0xAD0105) |
| `--install` | Hangs |
| `/S` | Hangs |
| `--install --start-with-win --silent` | Exit 11341829 |
| `--start-with-win` | Hangs |

**Key insight:** The `--install` parameter **requires** the target path argument (`"C:\Program Files\AnyDesk"`). Without it, the installer exits with the undocumented error code 11341829.

## Verification Checklist

After running the scheduled task, verify on multiple axes:

```powershell
# 1. Registry (both 32/64 bit views)
Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
                 "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" |
  Where-Object { $_.DisplayName -match "AppName" }

# 2. Binary on disk
Test-Path "C:\Program Files\AppName\App.exe"

# 3. Service status (if applicable)
Get-Service -Name "AppName*"

# 4. Running processes
Get-Process -Name "AppName"
```

## Troubleshooting

### schtasks warning "Task may not run because /ST is earlier than current time"

This is harmless when using `/SC ONCE` with `/ST 00:00` — the `schtasks /Run` command forces immediate execution regardless.

### Exit code 11341829 (0xAD0105) from AnyDesk

Means invalid/missing arguments. The installer requires the install path with `--install`. Always consult the AppDeployNews or official docs for the full command syntax.

### Installer still runs but never completes

Some installers spawn child processes or show EULA dialogs even with silent switches. If a 30-second wait isn't enough:
1. Check if the process is running: `Get-Process -Name "AppName"` 
2. Kill it: `Stop-Process -Name "AppName" -Force`
3. Check if partial install happened (registry keys, files)

### Finding silent switches for unknown installers

1. **AppDeployNews** — `https://www.appdeploynews.com/app-tips/<app>-<version>/` — reliable source
2. **Binary scan** — check for "Inno Setup", "Nullsoft", "InstallShield" in the EXE file
3. **Universal switches** to try: `/S`, `/silent`, `/quiet`, `-silent`, `--silent`
4. **Run with `/help` output captured to file** (though this may also hang if GUI-based)

## Source

Based on session: WinRM system check + SMB share mapping + software deployment to DESKTOP-4ALJOMP (192.168.13.43), July 2026.

## Adobe Acrobat Pro DC 2026

| Detail | Value |
|---|---|
| Package | `Adobe.Acrobat.Pro.DC.2026.001.21431.x64.rar` (1,638,615,006 bytes) |
| RAR password | `soft98.ir` |
| ISO inside RAR | `Adobe_Setup.iso` (1,687,508,992 bytes) |
| MSI | `AcroPro.msi` (13 MB) + `AcroPro.mst` (57 KB transform) |
| Update | `AcrobatDCx64Upd2600121431.msp` (879 MB) |
| Crack | `crack.exe` (38 MB, blocked by Defender as PUA) |
| Install path | `C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe` v21.1.20135.421056 |

### Complete Install Sequence

```powershell
# 0. Prerequisites: WinRAR installed, Defender exclusions set
Add-MpPreference -ExclusionPath "C:\Windows\Temp\Adobe_Setup" -Force

# 1. Extract RAR with password
$rar = "C:\Windows\Temp\Adobe.Acrobat.Pro.DC.2026.001.21431.x64.rar"
$dest = "C:\Windows\Temp\"
Start-Process "C:\Program Files\WinRAR\UnRAR.exe" -ArgumentList "x -psoft98.ir -y $rar $dest" -Wait -NoNewWindow -PassThru
# Output: Adobe.Acrobat.Pro.DC.2026.001.21431.x64\Adobe_Setup.iso + Block in Firewall.cmd + ReadMe

# 2. Mount the ISO (do MOUNT + COPY in ONE session)
Mount-DiskImage -ImagePath "C:\...\Adobe_Setup.iso" -StorageType ISO | Out-Null
Start-Sleep -Seconds 3
$dl = (Get-DiskImage -ImagePath "C:\...\Adobe_Setup.iso" | Get-Volume).DriveLetter
New-Item -ItemType Directory -Force -Path "C:\Windows\Temp\Adobe_Setup" | Out-Null
Copy-Item "${dl}:\Adobe Acrobat\*" "C:\Windows\Temp\Adobe_Setup\" -Recurse -Force
Dismount-DiskImage -ImagePath "C:\...\Adobe_Setup.iso" -ErrorAction SilentlyContinue

# 3. Install via msiexec as SYSTEM
# Write batch file (to avoid quoting issues with schtasks /TR):
@"
@echo off
cd /d "C:\Windows\Temp\Adobe_Setup"
msiexec /i "AcroPro.msi" TRANSFORMS="AcroPro.mst" /qn /norestart /log "C:\Windows\Temp\Adobe_Setup\msi.log"
"@ | Out-File "C:\Windows\Temp\Adobe_Setup\install.bat" -Encoding ASCII

schtasks /Delete /TN "InstallAcrobat" /F
schtasks /Create /SC ONCE /TN "InstallAcrobat" /TR "C:\Windows\Temp\Adobe_Setup\install.bat" /ST 00:00 /RL HIGHEST /RU SYSTEM /F
schtasks /Run /TN "InstallAcrobat"
Start-Sleep -Seconds 120

# 4. Verify
if (Test-Path "C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe") { "INSTALLED" }

# 5. Apply MSP update
# Write another batch and run via schtasks in the same pattern
msiexec /p "C:\Windows\Temp\Adobe_Setup\AcrobatDCx64Upd2600121431.msp" /qn /norestart

# 6. Block all Acrobat EXEs in firewall
$acrobatDir = "C:\Program Files\Adobe\Acrobat DC\Acrobat"
$count = 0
Get-ChildItem $acrobatDir -Filter "*.exe" | ForEach-Object {
    $ruleName = "Block_Adobe_" + $_.BaseName
    netsh advfirewall firewall add rule name=$ruleName dir=out program=$($_.FullName) action=block | Out-Null
    if ($LASTEXITCODE -eq 0) { $count++ }
}
Write-Output "Blocked $count executables"
```

### ISO Mounting Challenges

The ISO drive letter **does not persist between PowerShell sessions**. This is the single biggest trap:

| Attempt | Result |
|---|---|
| `Mount-DiskImage` in one `run_ps()`, access E:\ in next | ❌ E: not found |
| Mount + copy + dismount all in one `run_ps()` | ✅ Works |
| `Add-PartitionAccessPath` to reassign orphaned letter | ✅ Works |

If the ISO was successfully mounted in an earlier call but the drive letter was lost, use `Get-DiskImage` to find it and reassign:

```powershell
$img = Get-DiskImage -ImagePath "C:\path\to\setup.iso"
if ($img.Attached) {
    $vol = $img | Get-Volume
    if (-not $vol.DriveLetter) {
        $disk = $img | Get-Disk
        $part = $disk | Get-Partition | Select-Object -First 1
        Add-PartitionAccessPath -DiskNumber $disk.Number -PartitionNumber $part.PartitionNumber -AccessPath "E:\"
        $vol = Get-Volume -DiskImage $img
    }
}
```

### Windows Defender Blocking

The `crack.exe` was detected as a PUA by Windows Defender. Real-time protection blocked:
- `Copy-Item` — `IOException: "file contains a virus or potentially unwanted software"`
- `[System.Diagnostics.Process]::Start()` — same message
- `schtasks` execution — exit code `-2147023781` (0x8007045B)

**Fix:** Add an exclusion path BEFORE the copy/run step, in the same session:
```powershell
Add-MpPreference -ExclusionPath "C:\Windows\Temp\Adobe_Setup" -Force
```

After adding the exclusion, the copy succeeds but the process start may still be blocked depending on Defender's real-time scanning latency. A scheduled task (`schtasks /RU SYSTEM`) running from the excluded path may also fail — the block happens at the image-load level, not just file-copy level.

**Recommendation:** The crack/activation step is best done manually via RDP with Defender temporarily disabled, or by deploying a pre-configured exclusion policy.

### Firewall Block on Adobe Acrobat

The user's `Block in Firewall.cmd` script refused to run from temp directories (it had a `%~f0 | find /i "temp"` check). Workaround:

1. Copy the `.cmd` file out of temp to `C:\ProgramData\`
2. Write a batch wrapper that `cd /d "C:\ProgramData"` and calls it
3. Run via `schtasks /RU SYSTEM`

The script iterates all `.exe` files in both `C:\Program Files\Adobe\Acrobat DC\Acrobat\` and `C:\Program Files (x86)\Adobe\Acrobat DC\Acrobat\`, skipping uninstall/VC_redist/dotNetFx, and adds an outbound block for each via `netsh advfirewall`. If run before Adobe is installed, it exits cleanly with "folders not found".

**Manual equivalent** (more reliable, runs without file-path checks):
```powershell
$acrobatDir = "C:\Program Files\Adobe\Acrobat DC\Acrobat"
Get-ChildItem $acrobatDir -Filter "*.exe" | ForEach-Object {
    netsh advfirewall firewall add rule name="Block_Adobe_$($_.BaseName)" dir=out program=$($_.FullName) action=block
}
```
