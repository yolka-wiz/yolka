# Device CLI Commands Reference

This reference collects the most useful `show` / `get` / diagnostic
commands per device type for configuration backup and health checks.

## FortiGate (FortiOS)

```
# System identity
show system status
get system performance status

# Interfaces and routing
show system interface
show router static
show router info routing-table all

# Firewall
show firewall address
show firewall addrgrp
show firewall service category
show firewall service group
show firewall policy

# Management & services
show system admin
show system dns
show system ntp
show system ha

# Diagnostics
diagnose sys top-summary
diagnose hardware sysinfo memory
diagnose hardware sysinfo disk
show system session-info
```

**Pitfall:** FortiGate SSH works via `invoke_shell`, not `exec_command`.
The prompt may be `hostname $` (e.g. `FortiRad $`).

## Cisco IOS (Catalyst switches)

```
# Identity & platform
show version
show inventory
show env all

# Config
show running-config
show startup-config

# Interfaces & switching
show interfaces
show ip interface brief
show interfaces trunk
show vlan brief
show spanning-tree
show mac address-table
show etherchannel summary

# Neighbor discovery
show cdp neighbors
show lldp neighbors

# Health
show processes cpu
show memory statistics
show log
```

**Key step:** Send `terminal length 0` immediately after login to disable
paging. Otherwise `--More--` will block output collection.

## VMware ESXi

```
# Version & hardware
vmware -v
esxcli system version get
esxcli hardware platform get
esxcli system hostname get

# Networking
esxcli network ip interface list
esxcli network ip route ipv4 list
esxcli network vm list
esxcli network firewall ruleset list

# Storage
esxcli storage vmfs extent list
esxcli storage core device list
df -h

# Config
cat /etc/vmware/esx.conf
esxcli system syslog config get
```

## Linux (Ubuntu/Debian)

```
cat /etc/os-release
hostnamectl
uname -a
uptime
df -h
df -i
lsblk
lsblk -f
mount
cat /etc/fstab
ip a
ip route
cat /etc/resolv.conf
free -h
cat /proc/meminfo
lscpu
systemctl list-units --type=service --state=running
ss -tlnp
cat /etc/crontab
zpool list                     # if ZFS
cat /etc/rsnapshot.conf        # if rsnapshot
```

## Issabel / Asterisk VoIP

```
cat /etc/os-release
cat /etc/issabel-release
hostnamectl
asterisk -V
asterisk -rx "core show version"
asterisk -rx "core show channels"
asterisk -rx "core show calls"
asterisk -rx "sip show peers"
asterisk -rx "pjsip show endpoints"
asterisk -rx "queue show"
asterisk -rx "module show"
asterisk -rx "iax2 show peers"
cat /etc/asterisk/sip.conf
cat /etc/asterisk/extensions.conf
cat /etc/asterisk/queues.conf
ls -la /etc/asterisk/
```

## Windows / Veeam (via WinRM PowerShell)

```powershell
# System info
Get-ComputerInfo | Select-Object WindowsVersion, OsName, OsVersion, CsName, CsTotalPhysicalMemory | Format-List
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, LastBootUpTime | Format-List

# Disks
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID, @{N="SizeGB";E={[math]::Round($_.Size/1GB,2)}}, @{N="FreeGB";E={[math]::Round($_.FreeSpace/1GB,2)}}

# Network
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" }

# Services
Get-Service | Where-Object { $_.Status -eq "Running" }
Get-Service | Where-Object { $_.Name -match "Veeam|VBR" }

# Installed Veeam software
Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" 2>$null | Where-Object { $_.DisplayName -match "Veeam|Backup" }

# Veeam jobs
try { Add-PSSnapin VeeamPSSnapIn -ErrorAction Stop; Get-VBRJob | Format-Table } catch { "Snapin not available" }

# Shares & tasks
Get-SmbShare
Get-ScheduledTask | Where-Object { $_.TaskPath -match "Veeam|Backup" }

# Events
Get-WinEvent -LogName System -MaxEvents 20 | Where-Object { $_.LevelDisplayName -match "Error|Warning" }
```

**Avoid:** `Get-WindowsFeature` (hangs on some Windows versions).
**Avoid:** Unfiltered `Get-Module -ListAvailable` (very slow with many modules).
