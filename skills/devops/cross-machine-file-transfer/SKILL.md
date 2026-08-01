---
name: cross-machine-file-transfer
description: Transfer files between Windows machines when SMB shares are broken — HTTP server workarounds, WinRM PSSession copy, and FortiGate SMB inspection detection.
---

# Cross-Machine File Transfer (Windows)

## When to use

You need to copy installer files (1-2 GB) or small scripts between Windows machines, but:
- SMB shares give error 1702 "The binding handle is invalid"
- `net view \\server` fails
- `Test-NetConnection -Port 445` shows OPEN but `net use` fails with error 67

## Prerequisites

- WinRM access to BOTH machines (source and target)
- Admin credentials on both
- Port 5985 open on both

## Detection: Is it FortiGate SMB inspection?

1. On the **file server** (source), run:
   ```powershell
   netstat -ano | findstr :445
   ```
2. If most `ESTABLISHED` connections show the **firewall gateway IP** (e.g., `192.168.4.4:xxxxx`) instead of client IPs — the FortiGate is proxying SMB.

3. Confirm: `net view \\other-machine` returns error 1702 while `ping` and `Test-NetConnection -Port 445` succeed.

## Transfer Methods (ordered by preference)

### Option A: Python HTTP server (simplest — if Python on source)

On the source machine (file server):
```bash
cd /path/to/files
python -m http.server 8888
```

On the target machine:
```powershell
# PowerShell
Invoke-WebRequest -Uri "http://SOURCE_IP:8888/file.iso" -OutFile "C:\Windows\Temp\file.iso"

# curl (Windows 10+)
curl -o "C:\Windows\Temp\file.iso" "http://SOURCE_IP:8888/file.iso"
```

### Option B: PowerShell HttpListener (no Python needed)

Start on the source machine as a background job (via WinRM):
```powershell
Start-Job -ScriptBlock {
    $l = New-Object System.Net.HttpListener
    $l.Prefixes.Add("http://+:8888/")
    $l.Start()
    while($true) {
        $c = $l.GetContext()
        $p = $c.Request.Url.LocalPath.TrimStart('/')
        if ([String]::IsNullOrEmpty($p)) { $c.Response.StatusCode = 400; $c.Response.Close(); continue }
        $f = [IO.Path]::Combine("D:\Software", $p)
        if (Test-Path $f -PathType Leaf) {
            $d = [IO.File]::OpenRead($f)
            $c.Response.ContentType = "application/octet-stream"
            $c.Response.ContentLength64 = $d.Length
            $d.CopyTo($c.Response.OutputStream); $d.Close()
        } else { $c.Response.StatusCode = 404 }
        $c.Response.Close()
    }
} -Name FileServer
```

**Clean up after:**
```powershell
Stop-Job -Name FileServer; Remove-Job -Name FileServer
```

### Option C: WinRM PSSession Copy-Item

Works for small/medium files, but unreliable for 1GB+:
```powershell
$ss = New-PSSession -ComputerName SOURCE_IP -Credential (Get-Credential)
Copy-Item -FromSession $ss -Path "D:\path\file.iso" -Destination "C:\Windows\Temp\" -Recurse
Remove-PSSession $ss
```

**Limitation:** Can silently fail on large files (shows "Copy complete" but files don't appear).

### Option D: SMB with explicit credentials (if SMB works)

```powershell
$pass = ConvertTo-SecureString "PASSWORD" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("SOURCE_IP\username", $pass)
New-PSDrive -Name S -PSProvider FileSystem -Root "\\SOURCE_IP\Share" -Credential $cred | Out-Null
Copy-Item "S:\file.iso" "C:\Windows\Temp\file.iso" -Force
Remove-PSDrive -Name S -Force
```

## Pitfalls

- **PSSession copy** may report success while files are not actually transferred — verify with `Test-Path` or `dir` afterward
- **HttpListener job** stops when the PowerShell session ends — restart if needed between WinRM calls
- **Large files (1.6GB+)** over HTTP need generous timeout (5+ minutes) — use `Invoke-WebRequest -TimeoutSec 600`
- **Windows Defender** can block downloaded EXEs — add exclusion path before downloading
- **FortiGate SMB inspection** also breaks `Copy-Item -FromSession` over SMB protocol layers
