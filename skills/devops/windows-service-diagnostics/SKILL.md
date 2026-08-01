---
name: windows-service-diagnostics
description: "Systematic investigation, inventory, and auditing of Windows services — troubleshooting failures, mapping service ecosystems, auditing configurations, and documenting dependencies."
version: 1.1.0
author: Hermes Agent
platforms: [windows]
metadata:
  hermes:
    tags: [windows, services, troubleshooting, winrm, event-log, oracle, sql-server, inventory, audit, nservicebus]
    related_skills: [systematic-debugging, network-device-automation]
---

# Windows Service Diagnostics & Inventory

## When to Use

This skill covers two related classes of Windows service work:

**A. Service Failure Diagnostics** — One or more services fail to start and you need root cause, especially when:
- Services depend on external databases (Oracle, SQL Server)
- Services span multiple machines (app server + DB server)
- Some services start but others don't
- The error message is generic ("Failed to start service")

**B. Service Ecosystem Inventory & Audit** — You need a comprehensive picture of a service landscape:
- All services matching a naming pattern (e.g., `Barid.*`) across a machine
- Binary paths, config files, NServiceBus endpoint mappings, log configurations
- Cross-service dependency analysis (SCM + logical NServiceBus references)
- Oracle client/MSMQ/DataBus/environment auditing
- Documentation-generation from live data

## Investigation Workflow

### Phase 0 (Inventory-first): Service Ecosystem Discovery

When you have a naming pattern (e.g. `Barid.*`, `MyApp.*`), start with bulk discovery before diving into any single service.

#### 0.1 — Discover all services by pattern
```powershell
Get-CimInstance Win32_Service -Filter "Name LIKE 'Barid.%'" |
    Select-Object Name, PathName, StartName, State, StartMode, ProcessId, Description
```

Key fields to extract per service:
- `Name` — service name (SCM)
- `DisplayName` — human-readable
- `State` — Running / Stopped / Paused
- `StartMode` — Auto / Manual / Disabled
- `PathName` — binary path (often contains version info)
- `StartName` — service account
- `ProcessId` — PID if running
- `Description` — often contains product version string

#### 0.2 — Extract binary paths and identify service directories
```powershell
# Extract directory from quoted or unquoted binary paths
$path = $svc.PathName
if ($path -match '^"([^"]+)"') {
    $dir = [System.IO.Path]::GetDirectoryName($matches[1])
} elseif ($path -match '^([^ ]+\.exe)') {
    $dir = [System.IO.Path]::GetDirectoryName($matches[1])
}
# Group by unique directories to find version clusters
$uniqueDirs = $services | ForEach-Object {
    $dir = ...
} | Select-Object -Unique
```

#### 0.3 — Read config files from every service directory
```powershell
Get-ChildItem -Path $dir -Filter "*.config" -File |
    Where-Object { $_.Name -like '*.dll.config' -or $_.Name -like '*.exe.config' }
$xml = Get-Content $cfg.FullName -Raw
```

Key things to extract from configs:
- **Connection strings** — note if encrypted (`RsaProtectedConfigurationProvider`)
- **UnicastBusConfig / MessageEndpointMappings** — NServiceBus cross-service references
- **appSettings** — driver flags like `UseManagedOracleDriver`, file share paths
- **supportedRuntime** — .NET Framework target version
- **requirePermission** — XML config security flag

#### 0.4 — Build cross-service endpoint reference map
Use a reverse-index of all `Assembly -> Endpoint` mappings to identify the most-referenced services:
```python
for svc_name, mappings in svc_configs.items():
    for endpoint in mappings:
        refs[endpoint].add(svc_name)
# Sort by reference count — the most-depended-on services are the keystone endpoints
```

#### 0.5 — Check NLog.config in each service directory
```powershell
[nlog]? fileName=${basedir}/../logs/log.jlog  # typical jlog/xlog dual format
Get-ChildItem -Path $dir -Filter "*log*" -File  # actually see log files on disk
```

### Phase 1: Remote Access Setup

Use WinRM via pywinrm (`run_ps` for PowerShell commands):

```python
import winrm
s = winrm.Session("host", auth=("admin", "password"), transport="ntlm",
                   server_cert_validation="ignore")
r = s.run_ps("Get-Service -Name 'MyService' | Format-List Name,Status,StartType")
```

*NOTE:* `run_cmd` cannot handle PowerShell pipelines. Always use `run_ps`.
*NOTE:* Ping is usually blocked on Windows Server firewalls. Use `Test-NetConnection -Port` instead.

### Phase 2 (Inventory Path): Environment & Platform Audit

When building a complete inventory, go beyond individual services and check the shared infrastructure:

#### 2.1 — MSMQ Status
```powershell
# Check if MSMQ feature is installed
Get-WindowsFeature -Name MSMQ | Select-Object Name, Installed
# Check MSMQ service
Get-Service -Name MSMQ | Format-List Name, Status, StartType
# Check System.Messaging assembly availability
[System.Reflection.Assembly]::LoadWithPartialName("System.Messaging")
```

#### 2.2 — Oracle Client Inventory
```powershell
# Check environment variables at all scopes
[Environment]::GetEnvironmentVariable('TNS_ADMIN','Machine')
[Environment]::GetEnvironmentVariable('ORACLE_HOME','Machine')

# Find all Oracle.DataAccess.dll versions
Get-ChildItem -Path C:\ -Recurse -Filter "Oracle.DataAccess.dll" -ErrorAction SilentlyContinue

# Check tnsnames.ora
Get-ChildItem -Path C:\ -Recurse -Filter "tnsnames.ora" -ErrorAction SilentlyContinue
Get-Content (Get-ChildItem -Path C:\ -Recurse -Filter "tnsnames.ora" | Select-Object -First 1).FullName

# Check registry for Oracle installations
Get-ItemProperty HKLM:\SOFTWARE\ORACLE\* -ErrorAction SilentlyContinue |
    Select-Object PSChildName, ORACLE_HOME

# Check Programs and Features
Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" |
    Where-Object { $_.DisplayName -like "*Oracle*" } |
    Select-Object DisplayName, DisplayVersion
```

#### 2.3 — DataBus / Shared File Store Inspection
```powershell
# Check if shared data directory exists
Test-Path "C:\DataBus"
# List contents
Get-ChildItem "C:\DataBus" | Select-Object Name, Length, LastWriteTime
# Check NTFS permissions
(Get-Acl "C:\DataBus").Access |
    Select-Object IdentityReference, FileSystemRights, AccessControlType
# Check if it's an SMB share
Get-SmbShare -Name "DataBus" -ErrorAction SilentlyContinue
```

#### 2.4 — Environment Variable Cross-Check
Compare environment variables at all three scopes (Machine, User, Process). Service processes use the **Process** scope (which inherits from Machine):
```powershell
$vars = @('TNS_ADMIN','ORACLE_HOME','PATH','NLog_InternalLogFile')
foreach ($v in $vars) {
    $machine = [Environment]::GetEnvironmentVariable($v, 'Machine')
    $user = [Environment]::GetEnvironmentVariable($v, 'User')
    $process = [Environment]::GetEnvironmentVariable($v)
    Write-Output "$v: Machine=$machine | User=$user | Process=$process"
}
```

### Phase 4: Gather Service-Level Evidence (Diagnostics Path)

**First sweep — on the app server:**

1. **Check service status and start type:**
   ```powershell
   Get-Service -Name 'Prefix*' | Format-Table Name,Status,StartType -AutoSize
   ```

2. **Get full service details including binary path and account:**
   ```powershell
   Get-CimInstance Win32_Service -Filter "Name LIKE 'Prefix%'" |
       Select-Object Name, PathName, StartName, State, StartMode
   ```

3. **Check service dependencies:**
   ```powershell
   Get-Service -Name 'ServiceName' |
       Select-Object Name, ServicesDependedOn, DependentServices
   ```

4. **Check System event log (Service Control Manager errors):**
   ```powershell
   Get-WinEvent -FilterHashtable @{
       LogName='System'
       StartTime=([datetime]::Now.AddHours(-24))
       ProviderName='Service Control Manager'
   } -MaxEvents 50 | Where-Object { $_.Id -in 7000,7001,7009,7011,7023,7024,7031,7032,7034,7043 }
   ```

5. **Check Application event log (.NET / app errors):**
   ```powershell
   Get-WinEvent -FilterHashtable @{
       LogName='Application'
       StartTime=([datetime]::Now.AddHours(-24))
       Id=1026
   } -MaxEvents 10
   ```
   Event ID 1026 = .NET Runtime unhandled exception (gives full stack trace in message).

6. **Check Windows Error Reporting for crash details:**
   ```powershell
   Get-WinEvent -FilterHashtable @{
       LogName='Application'
       Id=1001
   } -MaxEvents 5
   ```
   WER shows APPCRASH details including faulting module and exception code. Exception code `e0434352` = .NET CLR exception.

### Phase 5: Investigate Service Application Layer

**Common information sources inside the service's working directory:**

| What to Check | Why |
|---|---|
| `*.dll.config` / `*.exe.config` files | Connection strings, app settings, NServiceBus endpoint mappings |
| `NLog.config` | Logging configuration (target file patterns, log levels) |
| `*.deps.json` files | .NET dependency info |
| log files on disk | Check file sizes and modification times |

#### 3.1 — Config File Bulk Extraction

When auditing multiple services, read the config from every service directory and extract structured data:

```powershell
$configFiles = Get-ChildItem -Path $dir -Filter "*.config" -File |
    Where-Object { $_.Name -like '*.dll.config' -or $_.Name -like '*.exe.config' }
foreach ($cfg in $configFiles) {
    $xml = Get-Content $cfg.FullName -Raw
    # Extract UnicastBusConfig / MessageEndpointMappings
    if ($xml -match '<UnicastBusConfig>(.*?)</UnicastBusConfig>') {
        $mappings = [regex]::Matches(
            $matches[1],
            'Assembly="([^"]*)"\s+Endpoint="([^"]*)"'
        )
    }
    # Extract connection strings
    if ($xml -match '<connectionStrings') {
        if ($xml -match 'configProtectionProvider') {
            # Encrypted - note the provider type (RsaProtectedConfigurationProvider)
        } else {
            # Plaintext - extract name + connectionString attributes
        }
    }
    # Extract supportedRuntime version
    if ($xml -match 'supportedRuntime version="([^"]*)"') {
        # Usually "v4.0" for .NET Framework services
    }
}
```

#### 3.2 — NServiceBus UnicastBusConfig Analysis

Each NServiceBus endpoint config has a `<UnicastBusConfig>` section with `<MessageEndpointMappings>`:

```xml
<UnicastBusConfig>
    <MessageEndpointMappings>
      <add Assembly="Barid.Fonix.Infrastructure" Endpoint="Barid.Fonix.Infrastructure" />
      <add Assembly="Barid.Fonix.NotificationCenter" Endpoint="Barid.Fonix.NotificationCenter" />
      <add Assembly="Barid.Fonix.Core.MessageBus" Endpoint="Barid.Fonix.RDS" />
    </MessageEndpointMappings>
</UnicastBusConfig>
```

Build a reverse reference index: which endpoints are referenced by how many services?
- Endpoints referenced by 10+ services are the **keystone services** (Infrastructure, NotificationCenter are common)
- Endpoints with 1 reference are typically leaf services
- Not all referenced endpoints necessarily exist as local Windows services — some may be on other machines or logical MSMQ queue names

#### 3.3 — NLog Configuration Audit

NLog.config files typically define multiple targets:

```xml
<target xsi:type="File" name="jlog"
        fileName="${basedir}/../logs/log.jlog"
        archiveFileName="${basedir}/../logs/log.{#}.jlog" />
```

Audit targets across all services:
- **fileName** — where logs are written
- **archiveFileName** — rotation pattern
- **Log levels** — from `<logger>` rules: Error, Warn, Info, Debug, Trace
- Check disk for actual log files — many may be 0 bytes (idle service or aggressive rotation)

**Connection strings may be encrypted** (`configProtectionProvider="RsaProtectedConfigurationProvider"`). If so:
- You can't read the actual connection string
- But the exception from `OracleConnection.Open()` still tells you what kind of error it is
- Look for appSettings keys like `UseManagedOracleDriver` to understand the driver strategy

**Key appSettings to check for Oracle:**
- `UseManagedOracleDriver` — `false` means unmanaged `Oracle.DataAccess.Client` (needs OCI + tnsnames.ora); missing means default (often managed driver)
- `ServerQueueName`, `FileSharePath`, `ConfigurationManager` — hints about architecture

### Phase 6: Check Dependent Systems

**When the service needs a database, check BOTH the app server AND the DB server:**

#### On the App Server

1. **TCP connectivity to DB:**
   ```powershell
   Test-NetConnection -ComputerName 192.168.x.x -Port 1521
   ```

2. **Oracle client installation:**
   ```powershell
   # Check registry for Oracle home
   Get-ItemProperty HKLM:\SOFTWARE\ORACLE\* -Name ORACLE_HOME
   # Check if tnsnames.ora exists
   Get-ChildItem -Path 'C:\' -Filter 'tnsnames.ora' -Recurse
   # Check environment variables
   [Environment]::GetEnvironmentVariable('TNS_ADMIN','Machine')
   [Environment]::GetEnvironmentVariable('ORACLE_HOME','Machine')
   ```

3. **Test Oracle.DataAccess directly (if installed):**
   ```powershell
   Add-Type -Path 'C:\odac64\odp.net\bin\4\Oracle.DataAccess.dll'
   $conn = New-Object Oracle.DataAccess.Client.OracleConnection(
       "Data Source=TNS_NAME;User Id=test;Password=test;")
   $conn.Open()  # ORA- error tells you what's wrong
   ```

#### On the DB Server

1. **Check Windows service for database:**
   ```powershell
   Get-Service -Name '*Oracle*' | Format-Table Name,Status
   ```

2. **Check listener:**
   ```powershell
   # Find lsnrctl
   $orahome = Get-ItemProperty HKLM:\SOFTWARE\ORACLE\* |
       Select-Object -ExpandProperty ORACLE_HOME -First 1
   & "$orahome\bin\lsnrctl.exe" STATUS
   ```

3. **Check database state via sqlplus:**
   ```powershell
   # Write SQL to temp file (use @''@ for literal $ signs)
   $sql = @'
   select 'STATUS=' || status from v$instance;
   select 'OPEN_MODE=' || open_mode from v$database;
   exit;
   '@
   Set-Content 'C:\Windows\Temp\check.sql' -Value $sql
   & "$orahome\bin\sqlplus.exe" -S '/ as sysdba' '@C:\Windows\Temp\check.sql'
   ```

4. **Check Oracle alert log:**

   Location: `<diagnostic_dest>\diag\rdbms\<dbname>\<instance>\trace\alert_<instance>.log`

   Find `diagnostic_dest`:
   ```sql
   select value from v$parameter where name = 'diagnostic_dest';
   ```
   (Works even when database is MOUNTED but not OPEN.)

### Phase 7: Common Root Causes

| Symptom | Likely Root Cause | Check |
|---|---|---|
| `OracleException` at `Open()` — generic | TNS name not resolved | tnsnames.ora exists? TNS_ADMIN set? |
| `ORA-01034: ORACLE not available` | Database instance not open | DB alert log; sqlplus connect locally |
| `ORA-03113: end-of-file` during OPEN | Instance crash on open | Alert log IMMEDIATELY before the 03113 |
| `ORA-19504` + `OS-112 no space` | Archive log destination full | Disk space on archive drive |
| `ORA-12154: TNS:could not resolve` | Missing tnsnames.ora | Check `TNS_ADMIN`, `ORACLE_HOME`, `network\admin` dir |
| Service starts but crashes after 30s | .NET runtime init error | Event ID 1026 for full stack trace |
| Some services start, others don't | Different driver configs or different init paths | Compare `UseManagedOracleDriver`, log files |

## Oracle-Specific Tips

### TNS Resolution Fix on App Server

1. Create `C:\<odac_or_home>\network\admin\tnsnames.ora`:
   ```
   DB_ALIAS =
     (DESCRIPTION =
       (ADDRESS = (PROTOCOL = TCP)(HOST = 192.168.x.x)(PORT = 1521))
       (CONNECT_DATA =
         (SERVER = DEDICATED)
         (SERVICE_NAME = service_name)
       )
     )
   ```

2. Set machine-level env vars (take effect on service restart):
   ```powershell
   [Environment]::SetEnvironmentVariable('TNS_ADMIN', 'C:\path\network\admin', 'Machine')
   [Environment]::SetEnvironmentVariable('ORACLE_HOME', 'C:\odac64', 'Machine')
   ```

3. Add ODAC path to system PATH:
   ```powershell
   $p = [Environment]::GetEnvironmentVariable('Path','Machine')
   if ($p -notlike '*odac64*') {
       [Environment]::SetEnvironmentVariable('Path', $p+';C:\odac64', 'Machine')
   }
   ```

### Oracle Alert Log Investigation

The alert log is the single most important source when Oracle fails to open. Look for errors just before `ORA-03113` or the `alter database open` entry. Common patterns:
- **ARCH error** + **OS-112**: Disk full on archive destination
- **ORA-00600**: Internal error (needs Oracle support)
- **ORA-01157** / **ORA-01110**: Datafile access issue (file missing, permissions)
- **ORA-01653** / **ORA-01683**: Tablespace full

### Archive Log Full Recovery

```
E: drive full → archiver can't write → database can't open
```

Steps (once E: has space again):
```
sqlplus '/ as sysdba'
startup mount;
alter database open;   -- Will complete once archiving works
```

To clear old archives (manual):
```powershell
Remove-Item 'E:\ARCHIVE\ARCHIVE_*' -Exclude '*873*'  # keep recent ones
```

## Common Pitfalls

- **Ping != connectivity** — Windows Server firewalls block ICMP. Always test TCP port.
- **`$` in SQL through PowerShell** — Use `@'...'@` single-quoted here-strings, not `@"..."@`. Otherwise `$variable` gets expanded.
- **Machine-level env vars** — Set via `[Environment]::SetEnvironmentVariable(..., 'Machine')` writes to registry. The service process must be restarted to pick them up. A simple `Restart-Service` is sufficient; reboot is NOT required.
- **ODAC vs full Oracle client** — ODAC puts `oci.dll` in the root, not in `bin\`. It needs ORACLE_HOME pointing to the ODAC root.
- **No `sc envadd`** — Not available on Windows Server 2022 or earlier. Use machine-level env vars instead.
- **Encrypted connection strings** — `RsaProtectedConfigurationProvider` means you can't read the connection string. The Oracle error code is still your best diagnostic.
- **Working vs failing services** — If some similar services start and others don't, compare their configs (especially `UseManagedOracleDriver`, `<connectionStrings>`, and whether they perform DB init at startup).
