# Case: Barid Service Startup Failure — Archive Log Full

## Environment

| Role | Hostname | IP | OS |
|---|---|---|---|
| App server | Parghar-app | 192.168.4.60 | Windows Server (hostname: Parghar-app) |
| DB server | Parghar-db | 192.168.4.61 | Windows Server, Oracle 19.15 (SID: pargar, service: pargar) |

## Symptoms

16 Barid NServiceBus .NET Windows services on the app server. Most are **Stopped** (Automatic start type). Two services (Email.Endpoint, Xch.Email.Endpoint) are **Running**. All services run as **LocalSystem**.

Attempting manual start produces:
```
Start-Service : Failed to start service 'Barid.Fonix.Infrastructure.Endpoint'
```

No dependency issues — `ServicesDependedOn` is empty.

## Investigation Trail

### Step 1: Application Event Log

Event ID 1026 — .NET Runtime unhandled exception:

```
Application: NServiceBus.Host.exe
Framework Version: v4.0.30319
Exception Info: Oracle.DataAccess.Client.OracleException
   at Oracle.DataAccess.Client.OracleException.HandleErrorHelper(...)
   at Oracle.DataAccess.Client.OracleConnection.Open()
   at NHibernate.Connection.DriverConnectionProvider.GetConnection(...)
   at NHibernate.Tool.hbm2ddl.SchemaMetadataUpdater.GetReservedWords(...)
   at Barid.Fonix.Core.Data.NHibernate.NHibernateDataAccess.GetSessionFactory(...)
```

Conclusion: **Oracle connection fails at NHibernate init.**

### Step 2: Service Configuration

```
Name: Barid.Fonix.Infrastructure.Endpoint
PathName: "D:\AUTOMATION\Fonix-11.01.29.41188\Packages\...\NServiceBus.Host.exe" ...
StartName: LocalSystem
State: Stopped
StartMode: Auto
```

All failing services have `<add key="UseManagedOracleDriver" value="false" />` in their `*.dll.config`.

Working services (Email, Xch.Email) have NO `UseManagedOracleDriver` key — they don't load Oracle modules at startup.

Connection strings are encrypted: `configProtectionProvider="RsaProtectedConfigurationProvider"`.

### Step 3: Oracle Client on App Server

- ODAC installed at `C:\odac64` (registry: `KEY_odac64`, `ORACLE_HOME=c:\odac64\`)
- `Oracle.DataAccess.dll` v4.112.3.0 in GAC (`GAC_64`)
- **No `network\admin\tnsnames.ora`** anywhere on the system
- **No `TNS_ADMIN` or `ORACLE_HOME` env vars** set (registry entry was unused)
- TCP connectivity to 192.168.4.61:1521: **succeeds**

### Step 4: Initial Fix (App Server)

Created `C:\odac64\network\admin\tnsnames.ora`:
```
PARGAR =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = 192.168.4.61)(PORT = 1521))
    (CONNECT_DATA = (SERVER = DEDICATED) (SERVICE_NAME = pargar))
  )
```

Set env vars:
```powershell
[Environment]::SetEnvironmentVariable('TNS_ADMIN','C:\odac64\network\admin','Machine')
[Environment]::SetEnvironmentVariable('ORACLE_HOME','C:\odac64','Machine')
# Add to PATH:
$p = [Environment]::GetEnvironmentVariable('Path','Machine')
if ($p -notlike '*odac64*') {
    [Environment]::SetEnvironmentVariable('Path', $p+';C:\odac64', 'Machine')
}
```

**Result:** Error changed from generic `OracleException` to `ORA-01034: ORACLE not available` — TNS resolution now works, connection reaches the database!

### Step 5: Database Investigation

On DB server, `OracleServicePARGAR` and `OracleOraDB19Home1TNSListener` are both **Running**.

But `sqlplus '/ as sysdba'` locally:
```
ERROR: ORA-01034: ORACLE not available
```

`startup mount;` succeeds, but `alter database open;` fails:
```
ORA-03113: end-of-file on communication channel
```

### Step 6: Alert Log (Root Cause)

Alert log at `D:\APP\ADMINISTRATOR\diag\rdbms\pargar\pargar\trace\alert_pargar.log`:

```
ORA-19504: failed to create file "E:\ARCHIVE\ARCHIVE_873_1.1200183835"
ORA-27044: unable to write the header block of file
OSD-04008: WriteFile() failure, unable to write to file
O/S-Error: (OS 112) There is not enough space on the disk.
```

**Root cause confirmed:** E: drive had only **128 MB free** (out of ~107 GB, with 849 archived redo logs filling the rest). Oracle can't open the database because it can't write the next archive log.

## Lessons

- **The error message at the app server changes after each fix** — this is progress, not failure. The changing ORA error code reveals more about where in the chain the real problem lives.
- **Services that start vs those that don't give you a control group** — compare configs between working and failing.
- **The real root cause was on a completely different server** — the DB server, not the app server. Multi-server debugging requires checking every layer.
- **Alert log location is NOT under Oracle Home on newer installs** — check `diagnostic_dest` in `v$parameter`.
- **Archive logs fill up silently** — no Windows alert, no Oracle warning until the database can't open.
