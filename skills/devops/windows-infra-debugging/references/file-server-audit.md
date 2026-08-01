# Windows File Server Audit via WinRM

## Overview

Systematic audit of a Windows file server (SMB shares) via remote WinRM investigation. Covers storage, shares, security, backups, and operational health — read-only inspection, no changes.

## System Baseline

```powershell
# OS, build, role
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
Write-Host "OS: $($os.Caption) Build:$($os.BuildNumber)"
Write-Host "System: $($cs.Manufacturer) $($cs.Model)"
Write-Host "RAM: $([math]::Round($cs.TotalPhysicalMemory/1GB))GB"
Write-Host "Procs: $($cs.NumberOfProcessors) phys, $($cs.NumberOfLogicalProcessors) logical"
Write-Host "Domain: $($cs.Domain)"
Write-Host "LastBoot: $($os.LastBootUpTime)"
```

### Key thresholds for a file server:
- **RAM < 8GB** = severely constrained. Windows Server file server RAM usage: 2-2.5GB OS base + SMB cache. Low RAM means every file request hits disk directly (no cache).
- **WORKGROUP** = no centralized auth. All user accounts are local, password/access management is manual.

## Storage Audit

### Logical Volumes
```powershell
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" |
    Select-Object DeviceID,
        @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}},
        @{N='FreeGB';E={[math]::Round($_.Freespace/1GB,1)}},
        @{N='PctFree';E={[math]::Round($_.Freespace/$_.Size*100,1)}},
        VolumeName, FileSystem
```

### Physical Disks (VMware/VM)
```powershell
Get-CimInstance Win32_DiskDrive | Select-Object Model, Size, MediaType, InterfaceType, Status
```

### Partition Map
```powershell
Get-CimInstance Win32_DiskPartition | Select-Object DiskIndex, Size, PrimaryPartition, Type, Bootable
```

### Red Flags

| Signal | Problem |
|--------|---------|
| D: or E: < 20% free | Users will hit out-of-space soon; SMB writes may fail |
| ReFS for a general-purpose or TEMP share | Wrong filesystem — ReFS has higher CPU/memory overhead and slower small-file I/O than NTFS. Use ReFS only for Veeam repositories or data requiring integrity validation |
| Drive with > 90% free | Over-provisioned, or VMware thin disk taking up datastore space for nothing |
| All volumes on separate single VMDKs | No redundancy at the virtual disk level |
| 512-byte sectors (not 4K) | May indicate older VMDK, sub-optimal for modern workloads |

## SMB Share Inventory

```powershell
Get-SmbShare | Select-Object Name, Path, Description, ShareType, ShareState,
    ConcurrentUserLimit, CachingMode | Format-Table -AutoSize
```

### Security Configuration
```powershell
Get-SmbServerConfiguration | Select-Object EnableSMB1Protocol, EnableSMB2Protocol,
    EncryptData, EnableSecuritySignature, RejectUnencryptedAccess
```

### Red Flags

| Signal | Problem |
|--------|---------|
| SMB1 enabled | Critical security risk — disable immediately |
| No Encryption + No Signing + WORKGROUP | All SMB traffic is plaintext on the LAN |
| `ConcurrentUserLimit` set low (e.g. 3) | Intentionally throttled, or accidental limiter from share creation |
| No description on custom shares | Harder to audit which share belongs to whom |

## Active SMB Sessions

```powershell
Get-SmbSession | Select-Object SessionId, ClientName, ClientUserName, NumOpens
```

Check for: stale sessions, unexpected clients, users with excessive open files.

## Local User Accounts

```powershell
Get-LocalUser | Select-Object Name, Enabled, LastLogon, PasswordLastSet | Format-Table -AutoSize
```

### Red Flags

| Signal | Problem |
|--------|---------|
| Enabled user with `LastLogon = null` | Never logged in — orphaned/forgotten account, security risk |
| User accounts that look like former employees | Access not cleaned up |
| No password expiry set | Policy gap in WORKGROUP environment |

## Backup & Recovery

### Volume Shadow Copies (VSS)
```powershell
vssadmin list shadows
# "No items found" = no restore points available
```

**This is critical** — without shadow copies, users have no "Previous Versions" capability and administrators have no fast rollback for accidental deletion.

### VSS Writers Status
```powershell
vssadmin list writers | findstr /i "Writer Name\|Last error\|Status"
```

All writers should show "Stable" status and "No error".

### Backup Agents & Schedules
```powershell
# Check running backup agents (ESET, Veeam, Acronis, etc.)
Get-Process | Where-Object { $_.ProcessName -match "eset|backup|vss|veeam|acronis|barid" }

# Scheduled tasks that look like backup jobs
Get-ScheduledTask | Where-Object { $_.TaskPath -match "backup|rman|archive" } |
    Format-Table TaskName, TaskPath, State
```

### Red Flags

| Signal | Problem |
|--------|---------|
| No VSS shadows | No user-facing restore capability |
| Backup agent service crashing repeatedly | Backup not running — check Event 7031/7032 |
| No backup-related scheduled tasks | No automated backup strategy |

## Event Log Health

### Critical/Error Events
```powershell
Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2} -MaxEvents 30 |
    Select-Object TimeCreated, Id, ProviderName, Message | Format-Table -AutoSize -Wrap
```

### Key Event IDs to watch

| ID | Source | Meaning |
|----|--------|---------|
| 7031 / 7032 | Service Control Manager | Service crashed unexpectedly and SCM can't restart it |
| 10010 | Microsoft-Windows-DistributedCOM | DCOM server registration timeout |
| 1801 | Microsoft-Windows-TPM-WMI | TPM/Secure Boot update issue (common on VMs, usually cosmetic) |
| 7 | Microsoft-Windows-Kernel-General | System time changed |

## Memory Analysis

```powershell
Get-CimInstance Win32_OperatingSystem |
    Select-Object TotalVisibleMemorySize, FreePhysicalMemory, FreeVirtualMemory, SizeStoredInPagingFiles
```

- Total / Free ratio: if < 25% free during idle, the server is undersized
- Page file size: should be at least 1.5x RAM for crash dumps
- If page file current usage is consistently > 0, RAM is insufficient

## Windows Feature Check

```powershell
# File server role
Get-WindowsFeature -Name FS-FileServer | Select-Object Name, Installed

# Deduplication (useful on file shares with many duplicates)
Get-WindowsFeature -Name FS-Data-Deduplication | Select-Object Name, Installed

# DFS (for multi-server file shares)
Get-WindowsFeature -Name FS-DFS* | Where-Object Installed | Select-Object Name, DisplayName
```

## Report Template

After gathering data, compile a findings table:

| # | Severity | Issue | Impact | Recommended Fix |
|---|---|---|---|---|
| 1 | HIGH | Description | What breaks | Action |
| 2 | MEDIUM | Description | What degrades | Action |
| 3 | LOW | Description | What to watch | Action |

Include: system profile table + storage layout + each finding with evidence (actual values from the server).
