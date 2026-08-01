# Barid Fonix System — Reference

**Two-server Windows production deployment of Barid Fonix (Iranian enterprise document management).**

## Server Topology

| Hostname | IP | Role | OS |
|----------|----|------|-----|
| `parghar-app` | 192.168.4.60 | Services (16 Barid NServiceBus services) | Windows Server 2022 |
| `parghar-db` | 192.168.4.61 | Oracle 19c (19.15.0.0.0) database | Windows Server 2022 |

**Credentials:** `administrator` / `Aa@123456` (NTLM WinRM auth, also works for RDP on 3389).

## Barid Services

16 Windows services named `Barid.*`, all run as **LocalSystem**. Each is a .NET 4.8 NServiceBus endpoint hosted by `NServiceBus.Host.exe`.

### By source directory

**Core suite** — `D:\AUTOMATION\Fonix-11.01.29.41188\Packages\*\AppServer\*\NServiceBus.Host.exe`:
- Correspondence, Email, Exchange, HelpCenter, HSM, Infrastructure, Mobile, RDS, Xch.Email
- Disabled: EnterpriseExchange, Infrastructure.AuditIntegrity
- STS: `BaridActiveSTS` at `D:\AUTOMATION\Fonix-11.01.29.41188\STS\ActiveSTS\Fonix.ActiveSTS\Barid.Fonix.ActiveSTS.WindowsService.exe`

**Separate deployments:**
| Service | Path | Version |
|---------|------|---------|
| Archive.EndPoint | `D:\ARCHIVE\Archive-11.02.12.41332\...` | 11.02.12.41332 |
| Calendar.Endpoint | `D:\CALENDER\Calendar-10.09.23.35390\...` | 10.09.23.35390 |
| DRG.Endpoint | `D:\DRG\DRG.Dashboard-10.05.05.28339\...` | 10.05.05.28339 |
| OFM.EndPoint | `D:\OFM\OFM-11.01.29.41170\...` | 11.01.29.41170 |

### Oracle driver mode

Config files in each endpoint directory: `Barid.Fonix.<Module>.Endpoint.dll.config`.

- Services with `UseManagedOracleDriver=false` → unmanaged `Oracle.DataAccess.Client` → needs tnsnames.ora
- Services WITHOUT this key → may not connect to Oracle at startup, or use default/fallback
- Connection strings are **RSA-encrypted** (`RsaProtectedConfigurationProvider`)

### Known connection: working vs non-working divide

**Could start without Oracle:** Email.Endpoint, Xch.Email.Endpoint (no `UseManagedOracleDriver` key, no NHibernate Oracle init at startup)
**Required Oracle at startup:** Infrastructure.Endpoint, Archive.EndPoint, Calendar.Endpoint, etc. (crash with `OracleException` if DB unreachable)

## Oracle Client (App Server)

**ODAC 11.2.0.3.0 64-bit** at `C:\odac64\`
- `Oracle.DataAccess.dll` v4.112.3.0 in GAC
- Native OCI DLLs at `C:\odac64\oci.dll` etc.
- tnsnames.ora: `C:\odac64\network\admin\tnsnames.ora` (created 2026-07-18 during outage)
- `$TNS_ADMIN` = `C:\odac64\network\admin` (machine-level env var)
- `$ORACLE_HOME` = `C:\odac64` (machine-level env var)

## Oracle Database (DB Server)

**Oracle 19c** — Home: `D:\App\db_home`, Base/ADR: `D:\APP\ADMINISTRATOR`
- Instance: PARGAR, SID: pargar, Service: pargar
- Listener: port 1521 on `parghar-db`
- Alert log: `D:\APP\ADMINISTRATOR\diag\rdbms\pargar\pargar\trace\alert_pargar.log`
- Data files: `D:\APP\ADMINISTRATOR\ORADATA\PARGAR\`
- Archive destination: `E:\ARCHIVE\` (was 99.9% full with 849 logs — root cause of the outage)

### TNS entry (on both servers)

```
PARGAR =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = 192.168.4.61)(PORT = 1521))
    (CONNECT_DATA = (SERVER = DEDICATED)(SERVICE_NAME = pargar))
  )
```

## Disk Layout

| Drive | Size | Purpose |
|-------|------|---------|
| C: | 100 GB | OS |
| D: | 200 GB | Oracle Home + Data files |
| E: | 100 GB | **Archive logs** (was full — root cause) |
| F: | 200 GB | New disk, partially used |

## Infrastructure

- **MSMQ**: Installed, service running (Automatic). NServiceBus uses MSMQ for inter-service messaging.
- **DataBus**: `C:\DataBus` — Everyone/FullControl ACL. NServiceBus large message payloads.
- **NLog**: Each service sends to UDP `127.0.0.1:9999` (NLogViewer), `127.0.0.1:9998` (JSON to Elastic), and local file `logfile*`. Config has `throwExceptions=true`.
- **DNS**: `parghar-db` → `192.168.4.61` resolves from app server. Also static hosts entry: `192.168.4.61 BaridPargarDB`.

## Outage History

**2026-07-18 — Archive disk full caused DB to not open**
1. E: drive 99.9% full with archived redo logs
2. Oracle could MOUNT but not OPEN (ORA-01034 → ORA-03113)
3. Barid services crashed at startup with `Oracle.DataAccess.Client.OracleException`
4. Fix: removed 800 old archive logs (94 GB freed), created missing tnsnames.ora on app server
