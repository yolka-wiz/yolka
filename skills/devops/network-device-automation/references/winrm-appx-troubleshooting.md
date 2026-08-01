# WinRM AppX & Store App Troubleshooting

## The `_x005F_` Path Encoding Bug

### Problem
When `pywinrm` sends PowerShell commands through its XML/SOAP transport, any file path containing `_x` in the string gets corrupted. The `_x` is interpreted as the start of a Unicode escape sequence, so `_x` becomes `_x005F_` (U+005F = underscore).

### Affected Paths
AppX package directories under `C:\Program Files\WindowsApps\` frequently contain `_x` in their names:
```
Microsoft.ScreenSketch_11.2307.52.0_x64__8wekyb3d8bbwe
                                    ^^
                                    this _x gets escaped
```

Result: PowerShell receives `..._x005F_x64__8wekyb3d8bbwe` and the file lookup fails.

### Workarounds

**Workaround 1: Environment variable (most reliable)**
```python
# Instead of inlining the path:
sess.run_ps('Add-AppxPackage -Register "C:\\...ScreenSketch_x64__...\\AppxManifest.xml"')

# Pass through an env var:
sess.run_ps('$env:PKG = "C:\\Program Files\\WindowsApps\\Microsoft.ScreenSketch_11.2307.52.0_x64__8wekyb3d8bbwe"; '
            'Add-AppxPackage -Register "$env:PKG\\AppxManifest.xml" -DisableDevelopmentMode')
```

**Workaround 2: `run_cmd` instead of `run_ps`**
```python
# cmd.exe doesn't apply XML encoding
sess.run_cmd('powershell -Command "Add-AppxPackage -Register \'...path...\'"')
```

## AppX Deployment in WinRM Sessions

### The Core Limitation
`Add-AppxPackage -Register` succeeds (returns normally) but `PackageUserInformation` remains empty `{}`. The package registers at the **system level** but **never deploys to any user profile**. This is because WinRM sessions are non-interactive and don't trigger the AppX user-provisioning pipeline.

### Detection
```powershell
Get-AppxPackage -Name Microsoft.ScreenSketch -AllUsers |
    Select-Object Name, Status, PackageUserInformation
```
- `Status: Ok` + `PackageUserInformation: {}` = registered but not deployed
- `Status: Ok` + `PackageUserInformation: {[User]: Installed}` = fully deployed

### Fix
```powershell
# Option 1: User logs out and back in
# Option 2: Scheduled task running as the interactive console user
schtasks /create /tn "DeployAppX" /tr "powershell -Command Add-AppxPackage -Register '...\\AppxManifest.xml' -DisableDevelopmentMode -ForceApplicationShutdown" /sc once /st 23:59 /ru "DOMAIN\\User" /it /f
schtasks /run /tn "DeployAppX"
```

### Important: `-AllUsers` is Destructive
`Remove-AppxPackage -AllUsers` physically deletes the package directory from `C:\Program Files\WindowsApps\`. If that was the only copy of the package on disk, it's gone and must be re-downloaded from the Microsoft Store.

## SnippingTool / ScreenSketch Specific Troubleshooting

### Error 0x87E10BC6
"Cannot create the process for package because an error was encountered while preparing for activation."

**Causes:**
1. Package not deployed to user profile (see above)
2. Executable referenced in manifest doesn't match files on disk
   - Newer versions (11.2307.52.0+) use `SnippingTool\SnippingTool.exe`
   - Older versions (11.2201.12.0) use `ScreenSketch.exe` at root
   - If the manifest says one but the directory only has the other, process creation fails

**Fix:** Re-register the correct version and ensure user deployment completes.

### Version History
| Package Version | Executable Path | Notes |
|---------------|----------------|-------|
| 11.2201.12.0 | `\ScreenSketch.exe` | Older SnippingTool exe name |
| 11.2307.52.0 | `\SnippingTool\SnippingTool.exe` | Newer, uses subfolder |
| 2024.401.617.0 | (provisioned only) | Latest store provisioned |

### Checking Executable Location
```powershell
Get-Content "C:\Program Files\WindowsApps\Microsoft.ScreenSketch_*\AppxManifest.xml" -TotalCount 30 |
    Select-String "Executable|EntryPoint"
```
