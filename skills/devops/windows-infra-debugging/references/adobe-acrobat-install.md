# Adobe Acrobat Pro DC 2026 — Remote Install via WinRM

## Files Needed

From the file share `\\192.168.4.100\Software\`:
```
Adobe.Acrobat.Pro.DC.2026.001.21431.x64.rar  (1.64 GB, pass: soft98.ir)
```

Extraction yields:
```
Adobe.Acrobat.Pro.DC.2026.001.21431.x64/
├── Adobe_Setup.iso          (1.68 GB)
├── Block in Firewall.cmd
├── ReadMe (How to Install).txt
└── Soft98.iR.url
```

ISO mount (`E:\Adobe Acrobat\`) contains:
```
AcroPro.msi                      (13 MB)  — main MSI
AcroPro.mst                      (57 KB)  — transform
Setup.exe                        (420 KB) — Adobe Setup wrapper
setup.ini                        (1 KB)   — config: msi=AcroPro.msi
AcrobatDCx64Upd2600121431.msp   (879 MB)  — update patch
crack.exe                        (38 MB)  — m0nkrus + MPT pre-activator
Core.cab, AlfSdPack.cab, ...     — CAB files (required by MSI)
```

## Install Steps

### 1. Disable Defender

```powershell
Set-MpPreference -DisableRealtimeMonitoring $true
Set-MpPreference -PUAProtection 0
Add-MpPreference -ExclusionPath "C:\Windows\Temp"
```

Check Tamper Protection on Win 11 if RT stays on.

### 2. Extract RAR

```powershell
# RAR nests into subfolder! Check path after extraction.
& "C:\Program Files\WinRAR\UnRAR.exe" x -psoft98.ir -y "C:\Windows\Temp\adobe.rar" "C:\Windows\Temp\Adobe_Extracted\"
# Result: C:\Windows\Temp\Adobe_Extracted\Adobe.Acrobat.Pro.DC.2026.001.21431.x64\Adobe_Setup.iso
```

### 3. Mount ISO + Copy All Files (ONE PowerShell session)

```powershell
Mount-DiskImage -ImagePath "$isoPath" -StorageType ISO
Start-Sleep 3
$dl = (Get-DiskImage -ImagePath "$isoPath" | Get-Volume).DriveLetter
# If no drive letter: Add-PartitionAccessPath to assign one
Copy-Item "${dl}:\Adobe Acrobat\*" "C:\Windows\Temp\Adobe_Setup\" -Recurse -Force
Dismount-DiskImage -ImagePath "$isoPath"
```

### 4. Install MSI (via schtasks as SYSTEM)

```powershell
schtasks /Create /SC ONCE /TN "InstallAcrobat" `
  /TR "msiexec /i C:\Windows\Temp\Adobe_Setup\AcroPro.msi TRANSFORMS=C:\Windows\Temp\Adobe_Setup\AcroPro.mst /qn /norestart" `
  /ST 00:00 /RL HIGHEST /RU SYSTEM /F
schtasks /Run /TN "InstallAcrobat"
```

### 5. Apply MSP Update

```powershell
schtasks /Create /SC ONCE /TN "AcrobatUpdate" `
  /TR "msiexec /p C:\Windows\Temp\Adobe_Setup\AcrobatDCx64Upd2600121431.msp /qn /norestart" `
  /ST 00:00 /RL HIGHEST /RU SYSTEM /F
```

### 6. Block Firewall (Outbound)

```powershell
Get-ChildItem "C:\Program Files\Adobe\Acrobat DC\Acrobat" -Filter "*.exe" | ForEach-Object {
    netsh advfirewall firewall add rule name="Block_Adobe_$($_.BaseName)" dir=out program=$($_.FullName) action=block
}
```

### 7. Stage crack.exe to Desktop

```powershell
Copy-Item "C:\Windows\Temp\Adobe_Setup\crack.exe" "C:\Users\Administrator\Desktop\crack.exe" -Force
```

The crack is GUI-only (m0nkrus + MPT) — cannot run via WinRM. User must double-click it.

## Verification

```powershell
# File + version
(Get-Item "C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe").VersionInfo.FileVersion
# Expected: 26.1.21431.0 after MSP update

# Firewall rules count
(netsh advfirewall firewall show rule name=all dir=out | Select-String "Block_Adobe_").Count
# Expected: ~16-18
```

## Known Issues

- **4 GB RAM VMs may OOM** during Copy-Item of large CABs + msiexec — WinRM disconnects; power-cycle from hypervisor
- **Defender blocks crack.exe** — add exclusion path *before* copy
- **m0nkrus cracks are GUI-only** — cannot automate the activation step
