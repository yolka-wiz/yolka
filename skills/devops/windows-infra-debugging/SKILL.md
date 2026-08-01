---
name: windows-infra-debugging
description: "Multi-server Windows infrastructure troubleshooting — services, databases, disk, and network layer investigation via WinRM."
version: 1.4.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [debugging, windows, infrastructure, services, database, oracle, winrm, troubleshooting, gpu, fileserver]
    related_skills: [systematic-debugging, network-device-management]
---

# Windows Infrastructure Debugging

## Overview

Debugging production Windows infrastructure (services, databases, disk) is fundamentally different from debugging code. You can't add a breakpoint, write a regression test, or `git bisect` a full disk. The investigative approach must be **layer-by-layer**, starting at the symptom and drilling down through each dependency.

**Core principle:** Reduce the set. Find what works vs what doesn't to narrow the search space. Then drill layer by layer: service → application log → OS → database → disk.

## When to Use

- Windows services won't start or crash repeatedly
- Database connections fail (Oracle, SQL Server)
- Only SOME instances of a service pattern work (partial outage)
- Services stuck in StartPending
- "ORA-xxxxx" errors after service startup
- Disk-full scenarios preventing application startup
- Post-reboot service failures

## Multi-Server Topology First

Before any investigation, establish the topology:

```
Which servers are involved?
  App server  →  (services, app logic)
  DB server   →  (database, archive storage)
  Other infra →  (load balancers, message queues, file shares)

What connects them?
  Ports: 1521 (Oracle), 1433 (SQL Server), 1801 (MSMQ), 445 (SMB)
  Hostnames/DNS: resolve IPs from each server's perspective
  Firewall: check connectivity even if ping fails (WinRM, test port)
```

**Action:** Use pywinrm via Python to reach each server. Ping/telnet may be blocked — use `Test-NetConnection -Port X` instead.

**Differential subnet check:** If a target host is unreachable on *all* checked ports (WinRM, RDP, SMB, ICMP), probe a known-reachable host on the **same subnet** (e.g. the subnet's gateway, firewall, or another server you already know responds). If that second host is also unreachable, the issue is at the network/firewall layer (VLAN routing, ACL, or intermediate firewall). If the second host responds, the issue is specific to the target (host offline, local firewall, IP changed). This single step cuts the search space in half immediately.

## Windows Machine Onboarding: First-Contact Audit

When connecting to a Windows machine for the **first time** — before any troubleshooting — run this systematic onboarding flow to establish the baseline and configure secure remote access.

### Phase 0: Reachability & Port Scan

Always port-scan before attempting WinRM — this distinguishes "host not on network" from "WinRM not running":

```python
import socket

target = "192.168.X.Y"
ports = [135, 445, 3389, 5985, 5986]

for port in ports:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect((target, port))
        print(f"Port {port:5d}: OPEN")
    except socket.timeout:
        print(f"Port {port:5d}: TIMEOUT")
    except ConnectionRefusedError:
        print(f"Port {port:5d}: REFUSED")
    except OSError as e:
        print(f"Port {port:5d}: {type(e).__name__} — {e}")
    finally:
        s.close()
```

| Port | Service | Expected |
|------|---------|----------|
| 135 | RPC Endpoint Mapper | OPEN |
| 445 | SMB | OPEN |
| 3389 | RDP | OPEN (if enabled) |
| **5985** | **WinRM HTTP** | **OPEN** |
| 5986 | WinRM HTTPS | OPEN / REFUSED |

**Retry timing:** Some machines take 30-90s after boot to fully come online. If the first scan shows *all* ports closed, **wait 10-30s and retry once** before concluding the host is offline.

### Phase 1: WinRM Connection

```python
import winrm

s = winrm.Session(
    "192.168.X.Y",
    auth=("administrator", "password"),
    transport="ntlm",
    server_cert_validation="ignore"
)
r = s.run_ps("hostname")
print(r.std_out.decode('utf-8', errors='replace').strip())
```

`run_ps()` is preferred over `run_cmd()` — it supports PowerShell pipelines and is more reliable for complex commands.

### Phase 2: Network & Firewall Inventory

```powershell
# Network adapters — identify the active interface(s)
Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, MacAddress, LinkSpeed | Format-Table -AutoSize

# IP configuration per interface
Get-NetIPConfiguration | Select-Object InterfaceAlias, IPv4Address, IPv4DefaultGateway

# Network profile (Domain / Private / Public) — determines which firewall profile is active
Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, NetworkCategory, IPv4Connectivity

# Firewall state per profile
netsh advfirewall show allprofiles state

# Any existing WinRM firewall rules
netsh advfirewall firewall show rule name="Windows Remote Management (HTTP-In)"
```

**Key insight:** The active network connection's profile (Domain/Private/Public) determines which firewall profile applies. A WiFi connection on the Private profile uses the Private firewall settings; the Public and Domain profiles are irrelevant for that connection.

### Phase 3: Firewall Configuration

If the firewall is OFF on the active profile, turn it ON *after* adding WinRM allow rules so you don't lose connectivity:

```powershell
# Safety: add WinRM rules FIRST, then enable the firewall
netsh advfirewall firewall add rule name="Windows Remote Management (HTTP-In)" dir=in protocol=tcp localport=5985 action=allow profile=private
netsh advfirewall firewall add rule name="Windows Remote Management (HTTPS-In)" dir=in protocol=tcp localport=5986 action=allow profile=private

# Then enable the firewall on the active profile
netsh advfirewall set privateprofile state on
```

Repeat for Domain or Public profiles as needed. Always add rules → enable firewall → verify WinRM still works.

### Phase 4: System Health Check

Run a comprehensive battery of health checks to establish a baseline:

```powershell
# OS version & build
Get-ComputerInfo | Select-Object WindowsVersion, WindowsEditionId, WindowsInstallationType, OsLastBootUpTime, OsBuildNumber

# Uptime
(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | Select-Object Days, Hours, Minutes

# CPU
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed, LoadPercentage

# Memory (KB)
Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory

# Disk (GB with free %)
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{n="SizeGB";e={[int]($_.Used/1GB+$_.Free/1GB)}}, @{n="UsedGB";e={[int]($_.Used/1GB)}}, @{n="FreeGB";e={[int]($_.Free/1GB)}}, @{n="FreePct";e={[int]($_.Free*100/($_.Used+$_.Free))}}

# Battery (laptops)
Get-CimInstance Win32_Battery | Select-Object Name, EstimatedChargeRemaining, BatteryStatus

# Antivirus
Get-CimInstance -Namespace root/SecurityCenter2 AntivirusProduct | Select-Object displayName

# DISM image health
dism /Online /Cleanup-Image /CheckHealth

# Pending reboot
$cb = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" -Name PendingFileRenameOperations -ErrorAction SilentlyContinue
if ($cb) { "REBOOT PENDING" } else { "No reboot pending" }

# Recent critical events (24h)
Get-WinEvent -FilterHashtable @{LogName="System"; Level=2; StartTime=(Get-Date).AddHours(-24)} -MaxEvents 20

# Stopped auto-start services
Get-Service | Where-Object { $_.StartType -eq "Automatic" -and $_.Status -ne "Running" }
```

**Note on disk commands from git-bash:** If the `$_.` in calculated properties gets rewritten by MSYS to `/c/Users/...`, escape the `$` with a backtick: `` `$_.Used ``. See the MSYS pitfall under "Tool Pattern: WinRM Investigation" below.

### Phase 5: Compile Findings

Collate into a structured report:
- **Reachability** — which ports are open, connection method
- **Interface inventory** — primary vs secondary interfaces, WiFi vs Ethernet
- **Firewall mapping** — which profile each interface uses, firewall state per profile
- **Health issues** — severity table (🟢/🟡/🔴) with findings and recommendations
- **Actions taken** — firewall enabled, rules added, any services started

---

## Tool Pattern: WinRM Investigation

```python
import winrm

s = winrm.Session(
    "192.168.X.Y",
    auth=("administrator", "password"),
    transport="ntlm",
    server_cert_validation="ignore"
)

# Run PowerShell — use run_ps() for pipeline commands, not run_cmd()
r = s.run_ps("Get-Service -Name 'Name*' | Format-Table Name,Status,StartType")
print(r.std_out.decode('utf-8', errors='replace'))
```

**Key pitfalls:**
- `run_cmd()` does NOT support PowerShell pipelines — use `run_ps()` instead
- Backslash paths in Python strings need raw strings (`r"..."`) or double escapes
- PowerShell heredocs with `$variable` need single-quoted `@'...'@` to avoid expansion
- Timeouts: set generous timeouts (30-120s) for service operations and database queries
- CLIXML in stderr is harmless — it's PowerShell progress output, not an actual error
- **MSYS path rewriting (git-bash):** When running PowerShell through the Hermes terminal tool (which runs inside git-bash on Windows), `$_.Property` gets rewritten by MSYS to `/c/Users/username.Property` — causing errors like `'No such file or directory'`. Symptoms: `Where-Object { $_.Status -eq 'Running' }` fails with `/c/Users/username.Status: command not found`. **Fix:** escape the `$` with a backtick `` `$_.Property `` in PowerShell commands passed through bash.

## The Layer-by-Layer Investigation Pattern

Start with the **visible symptom**, then drill down one layer at a time.

### Layer 1: Service Layer

```powershell
# List all services matching the pattern
Get-Service -Name 'Barid*' | Format-Table Name,Status,StartType

# Get full details (binary path, account, process ID)
Get-CimInstance Win32_Service -Filter "Name LIKE 'Barid%'"

# Try to start one and capture the error
Start-Service -Name 'Service.Name' -ErrorAction Stop
```

**Key signal:** If some services run and others don't, **list what's different** between them:
- Different binary paths? Different config directories?
- Different service accounts?
- Different `StartType`?
- Different `ServicesDependedOn`?
- Different `appSettings` (especially `UseManagedOracleDriver`)?

### Layer 2: Event Logs (Application + System)

Check BOTH the System log (SCM errors) and Application log (.NET Runtime):

```powershell
# Service Control Manager errors (last 12h)
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=([datetime]::Now.AddHours(-12)); ProviderName='Service Control Manager'} -MaxEvents 30 |
  Where-Object { $_.Id -in 7000,7001,7009,7011,7023,7024,7031,7032,7034,7043 }

# .NET Runtime crashes (Event ID 1026)
Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1026} -MaxEvents 5

# Application Error crashes (Event ID 1000)
Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000} -MaxEvents 5

# Windows Error Reporting (Event ID 1001)
Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1001} -MaxEvents 5
```

**.NET Runtime crash (Id=1026) gives the FULL STACK TRACE** — this is your most valuable signal. It will tell you:
- The exact exception type (e.g., `Oracle.DataAccess.Client.OracleException`)
- The failing method (`OracleConnection.Open()`)
- The complete call stack showing which component triggered it

### Layer 3: Service Configuration Files

Each Windows service has a binary path. Find the config files in that directory:

```powershell
# Get the binary path from the service
Get-CimInstance Win32_Service -Filter "Name='Service.Name'" | Select-Object PathName

# Look for *.dll.config and *.exe.config files
Get-ChildItem 'D:\Path\To\Service' -Filter '*.config'
```

**What to look for in config files:**
- `connectionStrings` — note if RSA-encrypted (`RsaProtectedConfigurationProvider`)
- `appSettings/add[@key='UseManagedOracleDriver']` — determines Oracle driver mode
- `UnicastBusConfig` — NServiceBus message endpoint mappings
- `Logging Threshold` — if "ERROR" only, you may miss warnings

### Layer 4: Database Layer

If the error points to a database (e.g., `OracleException`, `SqlException`):

```powershell
# On the DB server — check if the database is actually OPEN
# IMPORTANT: sqlplus heredocs ("<<") DON'T work over WinRM.
# Use this temp-file + pipe pattern:
$sql = @'
SET PAGESIZE 200 LINESIZE 300 FEEDBACK OFF ECHO OFF VERIFY OFF
SELECT STATUS FROM V$INSTANCE;
EXIT
'@
$tmpFile = [System.IO.Path]::GetTempFileName() + '.sql'
[System.IO.File]::WriteAllText($tmpFile, $sql)
$output = Get-Content $tmpFile | & 'D:\App\db_home\bin\sqlplus.exe' -S '/ as sysdba'
Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
Write-Output $output
# Expected: OPEN

# Alternative one-liner via cmd pipe (works but needs quoting care):
$env:ORACLE_SID='pargar'
echo "SELECT STATUS FROM V$INSTANCE;" | D:\App\db_home\bin\sqlplus.exe -S / as sysdba

# Find the ADR home first (see Layer 5B for alert log location)
```

**Critical WinRM+sqlplus pitfall:** Here-strings with `@'...'@` (single-quoted PS here-strings) prevent `$` expansion. The temp-file+pipe pattern is the most reliable approach — direct heredocs to sqlplus binary do NOT work over WinRM because the session doesn't have a true stdin to pipe from.

**Common Oracle root causes:**
| Symptom | Likely Cause | Check |
|---------|--------------|-------|
| ORA-01034 "ORACLE not available" | Instance not open | Alert log, disk space of archive destination |
| ORA-03113 "end-of-file" | Crash during OPEN | Alert log (usually disk space or data file issue) |
| ORA-12154 "TNS could not resolve" | No tnsnames.ora | `$TNS_ADMIN`, `$ORACLE_HOME` |
| ORA-19504/27044 "cannot create file" | Archive destination full | `Get-Volume -DriveLetter E` |

### Layer 5: Disk Layer

If the database won't open, check the archive destination disk:

```powershell
Get-Volume | Select-Object DriveLetter, SizeRemaining, Size
Get-ChildItem 'E:\\ARCHIVE' | Measure-Object -Property Length -Sum
```

**Action:** If archive disk is full, old archive logs can be safely removed if RMAN backups exist. Keep enough for potential recovery:

```powershell
# Move or delete old archive logs (oldest first)
Remove-Item 'E:\\ARCHIVE\\ARCHIVE_*' -Exclude 'ARCHIVE_<latest_pattern>*'
```

### Layer 5B: Oracle Comprehensive Analysis (ADR + Alert Log)

If the investigation requires an in-depth Oracle audit rather than just troubleshooting an outage:

```powershell
# ADR diagnostic destination
$env:ORACLE_SID='pargar'
$sql = "SELECT NAME, VALUE FROM V\$PARAMETER WHERE UPPER(NAME) LIKE '%DIAGNOSTIC%' OR UPPER(NAME) LIKE '%ADR%';"
echo $sql | D:\App\db_home\bin\sqlplus.exe -S / as sysdba

# Alert log — tail last 50 lines
$alert = 'D:\APP\ADMINISTRATOR\diag\rdbms\pargar\pargar\trace\alert_pargar.log'
Get-Content $alert -Tail 50

# Check alert and trace directory sizes (they grow over time)
Get-ChildItem 'D:\APP\ADMINISTRATOR\diag\rdbms\pargar\pargar' -Directory |
  Select-Object Name, @{N='SizeMB';E={
    [math]::Round((Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue |
      Measure-Object -Property Length -Sum).Sum / 1MB, 2)
  }} | Format-Table -AutoSize
```

## Oracle Comprehensive Analysis Checklist

When the task is to produce a **structured Oracle database analysis document** (not just fix an outage), follow this systematic multi-pass approach:

### Phase 1: Windows-Level Gathering

Query in parallel (no dependencies):

```powershell
# Services
Get-Service | Where-Object { $_.Name -like '*Oracle*' } | Format-Table Name,DisplayName,Status,StartType

# Registry — Oracle Home, SID, Base
Get-ItemProperty 'HKLM:\SOFTWARE\Oracle\KEY_OraDB19Home1' | Select-Object ORACLE_HOME, ORACLE_SID, ORACLE_BASE

# Disk layout
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -gt 0 } |
  Select-Object Name, @{N='SizeGB';E={[math]::Round(($_.Used+$_.Free)/1GB,2)}},
    @{N='UsedGB';E={[math]::Round($_.Used/1GB,2)}},
    @{N='FreeGB';E={[math]::Round($_.Free/1GB,2)}},
    @{N='PctFree';E={[math]::Round($_.Free/($_.Used+$_.Free)*100,1)}}

# Oracle directory tree (top two levels)
Get-ChildItem 'D:\APP' -Depth 2 -Directory | Format-Table FullName

# Service details with binary paths
Get-CimInstance Win32_Service | Where-Object { $_.Name -like '*Oracle*' } |
  Format-List Name, DisplayName, State, StartMode, PathName, ProcessId

# Scheduled tasks for RMAN/backup
Get-ScheduledTask | Where-Object { $_.TaskPath -like '*Rman*' -or $_.TaskName -like '*Archive*' } |
  Format-Table TaskName, TaskPath, State
```

### Phase 2: Oracle Config Files

Gather the networking configuration files:

```powershell
# tnsnames.ora
Get-Content 'D:\App\db_home\NETWORK\ADMIN\tnsnames.ora'

# listener.ora
Get-Content 'D:\App\db_home\NETWORK\ADMIN\listener.ora'

# sqlnet.ora
Get-Content 'D:\App\db_home\NETWORK\ADMIN\sqlnet.ora'
```

### Phase 3: SQL*Plus Database Queries

This is the most complex phase. The pattern that works over WinRM:

1. Write SQL script to a temp file
2. Pipe its content to sqlplus
3. Clean up

**Universal helper (Python via pywinrm):**

```python
import winrm, base64

session = winrm.Session(host, auth=(user, pw), transport='ntlm', server_cert_validation='ignore')

def run_sql(session, sql_content):
    """Execute Oracle SQL via WinRM — reliable temp-file+pipe pattern."""
    b64 = base64.b64encode(sql_content.encode('utf-16le')).decode('ascii')
    ps = f"""$sql = [System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String('{b64}'))
$tmp = [System.IO.Path]::GetTempFileName() + '.sql'
[System.IO.File]::WriteAllText($tmp, $sql)
$env:ORACLE_SID='pargar'
$out = Get-Content $tmp | & 'D:\\App\\db_home\\bin\\sqlplus.exe' -S '/ as sysdba'
Remove-Item $tmp -Force -ErrorAction SilentlyContinue
Write-Output $out"""
    r = session.run_ps(ps)
    return r.std_out.decode('utf-8', errors='replace').strip()
```

**Minimum SQL queries to run:**

```sql
-- 1. Instance & DB status
SELECT INSTANCE_NAME, HOST_NAME, VERSION, STATUS, DATABASE_STATUS,
       ARCHIVER, LOG_MODE, OPEN_MODE, PROTECTION_MODE, DATABASE_ROLE,
       STARTUP_TIME
FROM V$INSTANCE, V$DATABASE;

-- 2. Total DB size
SELECT ROUND(SUM(BYTES)/1024/1024/1024, 2) AS TOTAL_DB_SIZE_GB FROM V$DATAFILE;

-- 3. Tablespaces (name, type, status, extent management)
SELECT TABLESPACE_NAME, STATUS, CONTENTS, EXTENT_MANAGEMENT,
       ALLOCATION_TYPE, SEGMENT_SPACE_MANAGEMENT, BIGFILE
FROM DBA_TABLESPACES ORDER BY TABLESPACE_NAME;

-- 4. Tablespace sizes (allocated)
SELECT TABLESPACE_NAME,
       ROUND(SUM(BYTES)/1024/1024/1024, 2) AS TOTAL_GB,
       ROUND(SUM(DECODE(MAXBYTES,0,BYTES,MAXBYTES))/1024/1024/1024, 2) AS MAX_GB,
       COUNT(*) AS DATA_FILES
FROM DBA_DATA_FILES GROUP BY TABLESPACE_NAME
UNION ALL
SELECT TABLESPACE_NAME || ' (TEMP)',
       ROUND(SUM(BYTES)/1024/1024/1024, 2),
       ROUND(SUM(DECODE(MAXBYTES,0,BYTES,MAXBYTES))/1024/1024/1024, 2),
       COUNT(*)
FROM DBA_TEMP_FILES GROUP BY TABLESPACE_NAME
ORDER BY TABLESPACE_NAME;

-- 5. Data file locations
SELECT FILE#, NAME, STATUS, ENABLED, BYTES/1024/1024/1024 AS SIZE_GB
FROM V$DATAFILE ORDER BY FILE#;

-- 6. Control files
SELECT NAME, STATUS, IS_RECOVERY_DEST_FILE, BLOCK_SIZE, FILE_SIZE_BLKS
FROM V$CONTROLFILE;

-- 7. Redo log config
SELECT GROUP#, SEQUENCE#, BYTES/1024/1024/1024 AS SIZE_GB,
       MEMBERS, STATUS, ARCHIVED, THREAD#
FROM V$LOG ORDER BY GROUP#;

-- 8. Redo log member locations
SELECT GROUP#, MEMBER, STATUS, TYPE, IS_RECOVERY_DEST_FILE
FROM V$LOGFILE ORDER BY GROUP#, MEMBER;
```

For the full reference query bank, see `references/oracle-analysis-queries.sql`.

### Phase 4: Archive Log Audit

```powershell
# Archive log directory contents
Get-ChildItem 'E:\ARCHIVE' | Select-Object Mode, Length, Name | Format-Table -AutoSize
$files = Get-ChildItem 'E:\ARCHIVE' -File
"File count: $($files.Count)"
"Total size: $([math]::Round(($files | Measure-Object -Property Length -Sum).Sum / 1GB, 2)) GB"

# SQL queries for archive config
# See references/oracle-analysis-queries.sql for:
# - Archive destination config (V$ARCHIVE_DEST)
# - Archive format parameters (V$PARAMETER)
# - Recent archive logs (V$ARCHIVED_LOG)
# - FRA usage (V$RECOVERY_FILE_DEST)
```

### Phase 5: RMAN Backup Audit

Check RMAN configuration, backup scripts, and backup history:

**RMAN persistent config:**
```sql
SELECT NAME, VALUE FROM V$RMAN_CONFIGURATION ORDER BY NAME;
```

**Recent backup history:**
```sql
SELECT SESSION_KEY, INPUT_TYPE, STATUS, START_TIME, END_TIME,
       ELAPSED_SECONDS/3600 AS ELAPSED_HOURS,
       INPUT_BYTES/1024/1024/1024 AS INPUT_GB,
       OUTPUT_BYTES/1024/1024/1024 AS OUTPUT_GB
FROM V$RMAN_BACKUP_JOB_DETAILS
ORDER BY START_TIME DESC
FETCH FIRST 10 ROWS ONLY;
```

**RMAN backup scripts inventory** — check the batch directory:
```powershell
# Find RMAN scripts (.bat, .RCV, .txt) on common locations
Get-ChildItem 'E:\RMAN' -Recurse -Include '*.bat','*.RCV','*.txt'

# Read each script to understand backup strategy
Get-Content 'E:\RMAN\RMANBATCH\Full.RCV'
Get-Content 'E:\RMAN\RMANBATCH\differential.RCV'
Get-Content 'E:\RMAN\RMANBATCH\Delete.RCV'
Get-Content 'E:\RMAN\RMANBATCH\Config.txt'
```

**Task scheduler triggers** for backup jobs:
```powershell
$task = Get-ScheduledTask -TaskPath '\Rman\' -TaskName 'Full'
$task.Triggers | Select-Object Id, Enabled, @{N='Type';E={$_.GetType().Name}},
  StartBoundary, DaysOfWeek
```

### Phase 6: Users & Schemas

```sql
SELECT USERNAME, ACCOUNT_STATUS, DEFAULT_TABLESPACE, TEMPORARY_TABLESPACE,
       CREATED, PROFILE
FROM DBA_USERS
WHERE ORACLE_MAINTAINED = 'N'
ORDER BY USERNAME;
```

### Phase 7: Compile Structured Analysis Document

Use the documentation template from `references/oracle-analysis-queries.sql` and the "Post-Resolution" section below. The analysis document should have these sections:

| Section | Source |
|---|---|
| Installation & Version | Registry, SQL*Plus version, OPatch |
| Instance Status | `V$INSTANCE`, `V$DATABASE` |
| Tablespaces & Datafiles | `DBA_TABLESPACES`, `V$DATAFILE`, `DBA_DATA_FILES` |
| Control Files & Redo Logs | `V$CONTROLFILE`, `V$LOG`, `V$LOGFILE` |
| Listener & TNS Config | `listener.ora`, `tnsnames.ora`, `sqlnet.ora` |
| Archive Log Config | `V$ARCHIVE_DEST`, `V$PARAMETER`, `V$ARCHIVED_LOG`, disk `E:\ARCHIVE` |
| Disk Layout | `Get-PSDrive`, directory sizes |
| RMAN Config & Backups | `V$RMAN_CONFIGURATION`, scripts, task scheduler, `V$RMAN_BACKUP_JOB_DETAILS` |
| Observations & Risks | Missing patches, single archive dest, newly added empty drives, instance restart events |

**Save location pattern:** `~/playground/<project>/oracle/oracle-db-analysis.md`

### Phase 8: Key Observations to Surface

After gathering all data, synthesize these common risk patterns:

1. **Instance recently restarted** — check `STARTUP_TIME`; if within last 24h, alert log should be examined
2. **Archive log sequence gaps** — compare sequence numbers in `E:\ARCHIVE` vs `V$ARCHIVED_LOG`
3. **FRA underutilized** — if 0% used but configured, the database bypasses FRA for archive logs
4. **Only one archive destination** — risk: if that disk fails, archiving stops
5. **Redo log size** — 200 MB with only 3 groups = frequent log switches under load
6. **Control file autobackup age** — check `E:\controlfilerman\` for recency
7. **Empty newly added drives** — indicates a prior capacity issue was patched with a new disk, but data may not have been migrated yet
8. **Oracle Home patch age** — compare installed patches against Oracle's latest Critical Patch Updates

## The "Compare Working vs Non-Working" Pattern

This is the single most powerful technique for partial outages:

1. Identify a **working** instance and a **non-working** instance of the same service type
2. **List every difference** between them — don't dismiss anything as "probably unrelated"
3. The difference is almost certainly the root cause or a key clue

Example from a real session:
```
Working:    Barid.Fonix.Email.Endpoint     — appSetting: (no UseManagedOracleDriver)
Not working: Barid.Fonix.Infrastructure.Endpoint — appSetting: UseManagedOracleDriver=false
→ Root cause: unmanaged driver needs tnsnames.ora which was missing
```

## Parallel Subagent Dispatch for Evidence Gathering

For multi-server investigations, dispatch parallel subagents to gather evidence simultaneously:

```python
# Each subagent investigates one server or one layer
delegate_task(
    goal="Analyze services on app server",
    context="Credentials, what to check, what to report"
)
delegate_task(
    goal="Analyze database on DB server",
    context="Credentials, what to check, what to report"
)
```

**When to use parallel dispatch:**
- Investigating multiple servers
- Separating service-layer from database-layer evidence
- Gathering large amounts of data (raw WinRM dumps that would bloat your context)
- Both investigation and documentation compilation

## Common Windows Service Patterns

### NServiceBus Services (.NET)

Look for `NServiceBus.Host.exe` as the service binary. Key characteristics:
- Config lives in `*.dll.config` files (not `*.exe.config`) in the endpoint directory
- Connection strings may be RSA-encrypted (`RsaProtectedConfigurationProvider`)
- Services communicate via MSMQ queues (check MSMQ service: `Get-Service MSMQ`)
- Data bus fileshare: check `C:\DataBus` or configured `FileSharePath`
- Log files: look for `logfile*` and `NLog.config` in each endpoint directory

### Oracle Client (ODAC / ODP.NET)

| Setting | Driver | Needs tnsnames.ora |
|---------|--------|-------------------|
| `UseManagedOracleDriver=true` | `Oracle.ManagedDataAccess.dll` | Optional |
| `UseManagedOracleDriver=false` | `Oracle.DataAccess.Client` (unmanaged) | Yes |
| Setting absent | `Oracle.DataAccess.Client` (default) | Yes |

The unmanaged driver needs:
1. `tnsnames.ora` — check `C:\odac64\network\admin\` or wherever `$TNS_ADMIN` points
2. Native OCI libraries (`oci.dll` in `$ORACLE_HOME` or in PATH)
3. `TNS_ADMIN` env var set at machine level (requires service restart to pick up)

## Well-Known Oracle Errors Quick Ref

| Error | Meaning | First Thing to Check |
|-------|---------|---------------------|
| ORA-01034 | Database not open | Archive disk space |
| ORA-03113 | Connection lost during open | Alert log |
| ORA-12154 | TNS name not resolved | tnsnames.ora, TNS_ADMIN |
| ORA-12514 | Listener doesn't know service | listener.ora, service registration |
| ORA-19504 | Cannot create file | Disk space |
| ORA-27044 | Write header failure | Disk full / permissions |
| ORA-00283 | Recovery canceled | Check for media errors |
| ORA-00264 | No recovery required | Instance was clean shutdown |
| ORA-01081 | Already started | Do shutdown first |
| ORA-01219 | DB not open: fixed tables only | DB is in MOUNT not OPEN |

### Pitfalls

- **Don't assume ping failure = host down.** Windows Server often blocks ICMP. Use `Test-NetConnection -Port` instead.
- **`sc envadd` is NOT available on older Windows.** If you need to set env vars for a service, use registry or machine-level `[Environment]::SetEnvironmentVariable`.
- **Machine-level env vars require a service restart** to take effect — the SCM doesn't re-read them dynamically.
- **PowerShell here-strings**: use `@'...'@` (single-quoted) when the SQL contains `$` signs, or `$variable` gets expanded to empty.
- **`run_cmd()` in pywinrm does NOT support PowerShell pipelines.** Always use `run_ps()` for anything beyond simple commands.
- **CLIXML in stderr is not an error.** pywinrm returns PowerShell progress messages in stderr wrapped in CLIXML — ignore lines starting with `#< CLIXML`.
- **NLog.config may have `throwExceptions=true`.** This means NLog errors become fatal — check write permissions to log paths.
- **WinRAR extraction with password:** Use `UnRAR.exe x -p<PASSWORD> -y <ARCHIVE> <DEST>` — the `x` flag extracts with full paths, `-p` supplies the password, `-y` assumes yes to all prompts.
- **4 GB RAM VM limit:** Heavily-constrained VMs (4 GB) can become unresponsive during large file transfers (1.6 GB RAR extraction + ISO copy + MSI install). Plan for this: copy files in smaller batches if possible, or warn the user about crash risk.
- **Defender real-time protection** can block `Copy-Item` and `Start-Process` for files it considers PUA. Add an exclusion path BEFORE the operation.

### SMB Connectivity Troubleshooting

**"Binding handle is invalid" (error 1702):** When `net view \\server` gives error 1702 but `ping` and `Test-NetConnection -Port 445` succeed, the likely cause is a **FortiGate (or similar UTM) SMB inspection/proxy** intercepting port 445 traffic. On the file server, run:

```powershell
netstat -ano | findstr :445
```

If most established connections show the **firewall's IP** (not client IPs), the firewall is proxying SMB. Workaround: use HTTP file transfer (see `cross-machine-file-transfer` skill) or disable SMB inspection on the FortiGate policy.

### GPU / Display Diagnostics

Debugging GPU issues (stuttering, TDR, display link problems) on Windows via WinRM. Covers Memory Integrity / HVCI analysis, PCIe ASPM power management, nvidia-smi queries, Event Log TDR detection, monitor/EDID information, and display link training issues.

**See:** `references/gpu-diagnostics.md` — full checklist with PowerShell commands and root cause chain.

## File Server Audit

Systematic Windows file server (SMB shares) audit via WinRM. Covers storage layout, SMB share inventory and security, VSS/shadow copies, user account hygiene, backup agent health, event log errors, and memory constraints for file server workloads.

**See:** `references/file-server-audit.md` — full audit checklist with red flag tables.

## File Server — SMB & NTFS Permission Management

Creating users, removing stale accounts, and granting SMB+NTFS read-only access across
multiple shares in one operation. The key pattern: SMB share-level permission (Grant-SmbShareAccess)
alone is insufficient — you MUST also grant NTFS filesystem permissions (icacls) on the underlying
folder paths. The NTFS grant should use `(OI)(CI)(RX)` flags for inheritance to all child objects.

```powershell
# Create a read-only audit user
$pwd = ConvertTo-SecureString "password" -AsPlainText -Force
New-LocalUser -Name "readonly" -Password $pwd -PasswordNeverExpires -AccountNeverExpires

# Grant SMB share-level Read to every non-admin share
Get-SmbShare | Where-Object {$_.Name -notmatch '\\\$$|^IPC$'} | ForEach-Object {
    Grant-SmbShareAccess -Name $_.Name -AccountName "SERVERNAME\readonly" -AccessRight Read -Force
}

# Grant NTFS Read + Execute with inheritance on each share root
icacls "D:\SharePath" /grant "readonly:(OI)(CI)(RX)" /Q
```

**Pitfall:** `icacls /T` (recursive) will traverse the entire volume — slow on large drives.
Use `(OI)(CI)` flags without `/T` instead; inheritance flows to children automatically.

## Persian Engineering Folder Structure

Standardized Persian-language project folder structure designed for Iranian engineering firms
working on tenders (مناقصه) with AutoCAD DWG drawings. Solves the multi-engineer version-conflict
problem using an XREF-based single-source-of-truth pattern for base plans. Covers naming conventions,
project lifecycle folders, read-only audit user setup, and migration from flat personal-folder layouts.

**See:** `references/persian-engineering-folder-structure.md` — full template with 01_–07_ folder layout.

## Software Deployment via WinRM

Installing GUI-based software on a remote Windows machine via WinRM requires a different approach than local installation. WinRM sessions run in a non-interactive session context — GUI installers that try to show windows will either hang indefinitely or fail to start.

### Core Challenge

- `Start-Process -Wait` on a GUI installer **blocks** — the process waits for window messages that never arrive in a WinRM session
- Each `run_ps()` / `run_cmd()` call in pywinrm creates a **fresh PowerShell/cmd session** — PSDrive mappings, environment variables, and `net use` drives do NOT persist between calls
- Installers that require UAC elevation (even when the account is admin) will silently fail because WinRM runs with a filtered admin token

### Solution Pattern: Copy → Schedule → Verify

```
1. Copy installer to a local temp path (C:\Windows\Temp\)
2. Write a batch file (optional but helpful for complex commands)
3. Create a one-time scheduled task as SYSTEM (/RU SYSTEM /RL HIGHEST)
4. Run the task, wait for completion, verify
5. Clean up temp files and the task
```

**Why SYSTEM?** The SYSTEM account has full desktop interaction rights and bypasses UAC elevation blocks entirely. Even `RunAs` with admin credentials won't work reliably from a WinRM session.

### Step-by-step

```python
import winrm
import time

s = winrm.Session(host, auth=("user", "pass"), transport="ntlm")

def run_ps(cmd):
    r = s.run_ps(cmd)
    return r.std_out.decode('utf-8', errors='replace').strip()

# 1. Access SMB share with explicit credentials (PSDrive is ephemeral)
run_ps(
    '$pass = ConvertTo-SecureString "PASSWORD" -AsPlainText -Force; '
    '$cred = New-Object System.Management.Automation.PSCredential("DOMAIN\\user", $pass); '
    'New-PSDrive -Name S -PSProvider FileSystem -Root "\\\\SERVER\\Share" -Credential $cred | Out-Null; '
    'Copy-Item "S:\\installer.exe" "C:\\Windows\\Temp\\installer.exe" -Force'
)

# 2. Create and run scheduled task as SYSTEM
run_ps(
    'schtasks /Delete /TN "InstallApp" /F 2>&1 | Out-Null; '
    'schtasks /Create /SC ONCE /TN "InstallApp" '
    '/TR "C:\\Windows\\Temp\\installer.exe /S" '
    '/ST 00:00 /RL HIGHEST /RU SYSTEM /F 2>&1 | Out-Null; '
    'schtasks /Run /TN "InstallApp" 2>&1 | Out-Null'
)

# 3. Wait and verify
time.sleep(20)
```

**For complex installer commands** (paths with spaces, multiple switches), write a batch file on the remote machine first, then point the scheduled task at the batch file. This avoids quoting issues with `schtasks /TR`.

### Silent Install Switches (Common)

| Software | Silent Command |
|---|---|
| **WinRAR** | `installer.exe /S` |
| **AnyDesk** | `installer.exe --install "C:\Program Files\AnyDesk" --start-with-win --create-shortcuts --silent` |
| **7-Zip** | `installer.exe /S` |
| **VLC** | `installer.exe /L=1033 /S` |
| **Firefox** | `installer.exe /S` |
| **Chrome** | `installer.exe /silent /install` |
| **Adobe Reader** | `installer.exe /sPB /rs` |
| **Adobe Acrobat Pro (MSI)** | `msiexec /i "AcroPro.msi" TRANSFORMS="AcroPro.mst" /qn /norestart` |
| **Adobe Acrobat Pro (MSP update)** | `msiexec /p "update.msp" /qn /norestart` |

For unknown installers, run the EXE with `/?`, `--help`, or `/help` capturing output. If the installer is InnoSetup, look for "Inno Setup" in the binary string table; for NSIS look for "Nullsoft". Check `https://www.appdeploynews.com/app-tips/<app>-<version>/` for reliable silent switches.

### Verification

After installation, verify via multiple methods (not just registry):

```powershell
# Registry — 64-bit and 32-bit views
Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
                 "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" |
  Where-Object { $_.DisplayName -match "AppName" }

# Binary on disk
Test-Path "C:\Program Files\AppName\app.exe"

# Service (if applicable)
Get-Service -Name "AppName*"
```

### Pitfalls

- **schtasks /ST earlier than current time warning** is harmless — the `schtasks /Run` override runs it immediately anyway
- **schtasks may show "Queued" state** during long installs — this is normal, keep polling until "Ready"
- **Exit code 11341829 (0xAD0105)** from AnyDesk installer usually means wrong switches or missing required arguments — check the official docs for the correct silent syntax
- **Do NOT use `net use` for persistent drive mappings** in WinRM — they appear as "Unavailable" to the next command because the mapping is session-scoped
- **AppDeployNews.com** is a reliable source for silent install switches — check it when you're unsure
- **RAR extraction may create subfolders** — `UnRAR.exe x archive.rar` may nest files under a subdirectory named after the archive. Always `Get-ChildItem` the extraction target to verify the real path before proceeding
- **Dual-NIC machines** (Wi-Fi + Ethernet) may have multiple active IPs — track *both* addresses. The WinRM target IP may change if the user switches networks or cables
- **m0nkrus/MPT crack executables are GUI-only** — they check for interactive desktop and cannot run via WinRM or schtasks. Always copy them to the interactive user's Desktop (`C:\Users\<username>\Desktop\`) and instruct the user to double-click

### ISO Mounting over WinRM

ISO images mounted via `Mount-DiskImage` **lose their drive letter between PowerShell sessions**. Each `run_ps()` call starts a fresh session, so the drive letter assigned in one call is gone in the next:

```powershell
# WRONG — drive letter E: lost between calls
run_ps("Mount-DiskImage -ImagePath 'setup.iso'")  # E: assigned
run_ps("Get-ChildItem E:\\")                        # E: not found!

# RIGHT — entire operation in one session
run_ps(
    'Mount-DiskImage -ImagePath "setup.iso" | Out-Null; '
    'Start-Sleep -Seconds 3; '
    '$dl = (Get-DiskImage -ImagePath "setup.iso" | Get-Volume).DriveLetter; '
    'Copy-Item "${dl}:\\*" "C:\\Temp\\Setup\\" -Recurse -Force'
)
```

If the drive letter was already used by a prior mount that got orphaned, reassign it:

```powershell
$img = Get-DiskImage -ImagePath "setup.iso"
$disk = $img | Get-Disk
$part = $disk | Get-Partition | Select-Object -First 1
Add-PartitionAccessPath -DiskNumber $disk.Number -PartitionNumber $part.PartitionNumber -AccessPath "E:\\"
```

### Windows Defender Blocking Installers / Cracks

Defender's real-time protection blocks execution of files it detects as PUA (Potentially Unwanted Application) or malware. This typically hits crack/patch executables:

| Symptom | Error |
|---|---|
| `.NET Process.Start()` | `"Operation did not complete successfully because the file contains a virus or potentially unwanted software"` |
| `schtasks` exit code | `-2147023781` (0x8007045B) |
| `Copy-Item` | `IOException: "file contains a virus or potentially unwanted software"` |

**Workaround — add an exclusion before copying/running:**

```powershell
Add-MpPreference -ExclusionPath "C:\Windows\Temp\Adobe_Setup" -Force
```

This should be done in the **same session** as the copy/run step, or better yet, configure it before the deployment task is created.

**Win 11 Tamper Protection** — On Windows 11 (and some Win 10 builds with Tamper Protection enabled), `Set-MpPreference -DisableRealtimeMonitoring $true` **silently fails**. The command returns exit 0 but real-time monitoring stays on because Tamper Protection overrides it.

- Detection: `(Get-MpPreference).DisableRealtimeMonitoring` returns `True` but real-time scans still block files
- No PowerShell bypass exists — user must toggle **Tamper Protection** to **Off** in **Windows Security → Virus & threat protection → Manage settings**
- Partial workaround: `Set-MpPreference -PUAProtection 0` and `Add-MpPreference -ExclusionPath` can reduce false positives enough for the crack/staged exe to survive copy and run when double-clicked

### Firewall Blocking All Executables in a Directory

To block an application from phoning home (outbound), enumerate all `.exe` files in its install directory and add a `netsh` rule per file:

```powershell
$acrobatDir = "C:\Program Files\Adobe\Acrobat DC\Acrobat"
Get-ChildItem $acrobatDir -Filter "*.exe" | ForEach-Object {
    $ruleName = "Block_" + $_.BaseName
    netsh advfirewall firewall add rule name=$ruleName dir=out program=$($_.FullName) action=block
}
```

Exclude uninstaller and redistributable EXEs to avoid breaking uninstall or VCRT.

For detailed session examples and per-app troubleshooting, see `references/software-deployment-via-winrm.md`.

## Post-Resolution: System Documentation Handoff

After resolving the outage, compile a **structured system analysis** into a git repo. This ensures future agents (or humans) can understand the full architecture without needing live server access.

### What to document

| Section | Contents |
|---|---|
| **Services analysis** | All services: names, paths, accounts, configs, NServiceBus mappings, log config |
| **Database analysis** | Oracle/SQL Server config, listener, TNS, archive setup, disk layout, alert log location |
| **Infrastructure integration** | Architecture diagram, network ports, hostnames, env vars, connection flow |
| **Troubleshooting guide** | Symptom → checklist → fix for each known failure mode |
| **Raw evidence** | JSON dump of WinRM investigation output (optional, useful as reference) |

### Repo structure pattern

```
project-name/
├── README.md                  ← Overview, quick-ref commands, credentials note
├── services/
│   └── services-analysis.md   ← Full service inventory with tables
├── database/
│   └── db-analysis.md         ← DB config, listener, TNS, alert log
└── docs/
    └── infrastructure.md      ← Architecture, network, troubleshooting guide
```

### How to build it

1. **Dispatch parallel subagents** for evidence gathering while investigation is fresh:
   - One subagent per server or per layer (services, database, infra)
   - Each writes a markdown file to the repo

2. **Compile and cross-reference** — note connections between layers (e.g., "Service X uses `UseManagedOracleDriver=false` which requires tnsnames.ora on the app server, pointing to Oracle DB on server Y")

3. **Document the outage** — what happened, investigation trail, root cause, fix applied. This is the most valuable part for future troubleshooting.

4. **Commit with descriptive messages** — link the commit to the outage date and root cause

5. **Declare the repo location** to the user in their terminal so they know where it lives
