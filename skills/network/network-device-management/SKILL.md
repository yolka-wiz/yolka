---
name: network-device-management
description: Backup, inspect, and troubleshoot network infrastructure devices (Cisco, Fortigate, ESXi, VoIP, Windows) via SSH, Telnet, and WinRM — including legacy-SSH recovery on old IOS.
---

# Network Device Management

Collect configs from, troubleshoot connectivity to, and document network infrastructure devices across a heterogeneous fleet. Covers Cisco switches (IOS 12.x/15.x), Fortigate firewalls, ESXi servers, Linux backup servers, Issabel5 VoIP, and Windows Veeam servers.

## Triggers

- User provides an inventory CSV of network devices and asks for backup/documentation
- User asks to "discover" or "map" the network (use FortiGate DHCP API — see Phase 0)
- User provides FortiGate credentials and asks what's on the network
- User reports SSH failures to legacy Cisco switches
- User needs to inspect device configs without making changes
- User needs to regenerate Cisco SSH RSA keys on devices with broken SSH
- User reports video lag, stutter, or intermittent display issues on a Windows computer
- User says "unplugging and replugging the display cable fixes it temporarily"

## Workflow

### Phase 0: Network Discovery (when no inventory exists)

When the user has not provided an inventory but has FortiGate/firewall credentials, discover the entire LAN layout from scratch:

1. **Login to FortiGate API:**
   ```bash
   curl -sk -c /tmp/fg-cookies -b /tmp/fg-cookies \
     -d "username=<user>&secretkey=<pass>" \
     "https://<fortigate-ip>/logincheck"
   ```

2. **Dump all DHCP leases** (gives MAC, hostname, VCI, VLAN/interface for every device):
   ```bash
   curl -sk -b /tmp/fg-cookies \
     "https://<fortigate-ip>/api/v2/monitor/system/dhcp"
   ```

3. **Identify Windows machines** by VCI field: `"MSFT 5.0"` = Windows DHCP client. Note the hostname and VLAN (`interface` field) for each.

4. **Build a network topology map** from the interface names:
   - VLANs with `MSFT 5.0` clients → Windows LANs
   - VLANs with `yealink` clients → VoIP phones
   - VLANs with `ubnt` clients → Ubiquiti APs
   - VLANs with `udhcp 1.26.x` clients → embedded Linux
   - Reserved IPs → static infrastructure servers

5. **Port-scan identified Windows IPs** from a machine on a routed subnet:
   ```bash
   for ip in <windows-ips>; do
     timeout 2 bash -c "echo > /dev/tcp/$ip/5985" 2>/dev/null && echo "$ip:5985 OPEN"
   done
   ```

6. **Test WinRM credentials** across VLANs using pywinrm (works through FortiGate inter-VLAN routing as long as policy allows TCP 5985):
   ```python
   import winrm
   s = winrm.Session(ip, auth=("administrator", password),
                     transport="ntlm", server_cert_validation="ignore")
   r = s.run_cmd("hostname")
   print(r.std_out.decode())
   ```

7. **Gather system info** from each connected machine for a complete inventory:\n   - OS version: `wmic os get Caption,Version /format:csv`\n   - PS version: `powershell -NoProfile -Command $PSVersionTable.PSVersion`\n   - IP config: `ipconfig | findstr IPv4`\n\n8. **Fingerprint unknown devices** from the DHCP lease table, port banners, and MAC addresses:\n   - **VCI** (Vendor Class Identifier in DHCP lease):\n     - `MSFT 5.0` = Windows\n     - `yealink` = VoIP phone (Yealink)\n     - `ubnt` = Ubiquiti access point\n     - `udhcp 1.26.x` = embedded Linux (printers, IoT)\n     - `android-dhcp-*` = Android device\n   - **MAC OUI** (first 3 hex bytes):\n     - `00:0c:29` = VMware VM **→ there is an ESXi host somewhere** (find it via subnet scan or FortiGate)\n     - `90:6c:ac` = Fortinet\n     - `24:e9:b3` = Cisco\n     - `d0:21:f9` = Ubiquiti\n     - `58:38:79` = HP/Ricoh printers\n     - `80:5e:0c` = Yealink VoIP\n   - **SSH banner** (connect to port 22):\n     - `SSH-2.0-Cisco-1.25` = Cisco IOS\n     - `SSH-2.0-dropbear_20xx` = Dropbear (Ubiquiti, embedded)\n     - `SSH-2.0-OpenSSH_*` = standard Linux/BSD\n   - **HTTP Server header**:\n     - `Server: cisco-IOS` + realm `level_15_access` = Cisco IOS web\n     - `Server: Apache` + `Location: /ng` = FortiOS (FortiGate)\n     - `Server: bsa/1.2` + redirect to `index.asp` = Printer\n     - `Server: Apache-Coyote` + XML on `:8080` = Veeam REST API\n\n9. **For a complete subnet scan** (when DHCP doesn't cover all devices):\n   ```bash\n   for i in $(seq 1 254); do\n     ping -c 1 -W 1 "192.168.x.$i" 2>/dev/null | grep -q "1 received" && echo "UP: 192.168.x.$i" &\n   done\n   wait\n   ```\n   Then port-scan each UP host for common service ports to identify the device type.\n\n**Pitfall:** The initial ping test is not sufficient for cross-VLAN WinRM connectivity. The FortiGate policy may allow ICMP but block TCP 5985. Always follow up with a port test: `timeout 2 bash -c "echo > /dev/tcp/<ip>/5985"`.

**Pitfall:** FortiGate API write operations (CMDB PUT to `/api/v2/cmdb/`) may time out or return HTTP 403 on v6.2.x even when read operations (monitor at `/api/v2/monitor/`) work fine. The session cookie has read-only scope. Use SSH + expect for admin config changes (see `references/fortigate-cli-expect.md`).

**Pitfall:** pywinrm's NTLM transport requires the **client** machine's WinRM TrustedHosts list to include the target IP, OR use HTTPS transport. Run PowerShell on the client: `Set-Item WSMan:\\localhost\\Client\\TrustedHosts -Value <target-ip> -Force` (needs admin rights on the client, not the target). Cross-VLAN WinRM may fail if the FortiGate policy doesn't allow port 5985 between VLANs even when ICMP passes — the initial ping test is not sufficient.

**FortiGate CLI config via expect:** When the API write endpoint returns 403, use expect to drive the FortiGate CLI over SSH. See `references/fortigate-cli-expect.md` for complete scripts for SSH key injection, address object creation, and address group membership management.

### Phase 1: Inventory & Connectivity Check

1. Parse the device inventory CSV to extract host, username, password, protocol
   - Common format: `Group | Title | Username | Password | URL | Notes | TOTP | Tags | Icon`
   - Tags field (`website`, `ssh`, `rdp`) indicates access protocol
   - Title field often encodes the IP: `esxi10.bornarad.co` → hostname `esxi10`, subdomain `bornarad.co`
   - Group prefixes (`VM`, `HW`, `Website`) classify the device type
2. Ping/connectivity check all devices first
3. Install required tools:
   - `paramiko` for SSH
   - `telnetlib3` or raw-socket Telnet for Cisco
   - `pywinrm` for Windows WinRM
4. Create a backup directory tree: `~/Documents/backup/<device-type>/`

### Phase 2: Config Collection by Protocol

**SSH (Linux, ESXi, Fortigate, Issabel):**
- Use `paramiko.SSHClient` with `exec_command()` for standard Linux servers
- Use `invoke_shell()` with timeout-guarded `recv()` loops for devices with interactive CLI (Fortigate)
- **For ESXi:** prefer the `ssh` CLI tool with key-based auth (ESXi's embedded SSH is minimal; paramiko works but CLI SSH gives better compatibility with `vim-cmd` and `esxcli` which may produce very wide output)
- Run device-specific commands (see command lists below)

**Telnet (Cisco switches):**
- Raw socket to port 23 with IAC negotiation filtering
- Important: IAC (Interpret As Command) bytes (0xFF) need to be filtered from output
- Send `terminal length 0` immediately to disable paging
- Login: send username → wait for password prompt → send password
- Send `enable` if only `>` prompt received

**WinRM (Windows servers):**
- Use `pywinrm.Session` with `transport='ntlm'`
- Try HTTP (5985) first, fallback to HTTPS (5986)
- Send PowerShell commands via `session.run_ps()`

**GPU Diagnostics (via WinRM):**
- See `references/windows-gpu-diagnostics.md` for the full diagnostic workflow
- Stack: pywinrm → nvidia-smi → WMI → PowerShell → event logs → powercfg
- Common root causes to check in order: HVCI/Memory Integrity status (Win32_DeviceGuard), PCIe ASPM setting (powercfg), PCIe link speed under load (nvidia-smi --query-gpu=pcie.*), event log TDR events (wevtutil), monitor EDID (WmiMonitorID)

### Phase 3: Documentation Generation

- Extract key info (versions, hostnames, interfaces, policies, routes) from collected configs
- Generate a single Markdown document with device summaries
- Include an ASCII network topology diagram
- List backup file manifest with sizes

### Phase 4: SSH Recovery on Legacy Cisco Switches

When SSH fails with "no matching key exchange" or "Invalid key length" on old Cisco IOS:

1. **Diagnosis via Telnet:**
   ```bash
   # Connect via telnet (Python raw socket)
   # Check SSH status
   show ip ssh
   # Check RSA key size
   show crypto key mypubkey rsa
   ```

2. **Root causes** (increasing severity):
   - `KexAlgorithms`: switch only offers `diffie-hellman-group1-sha1`
   - `HostKeyAlgorithms`: switch only offers `ssh-rsa`
   - `Ciphers`: switch only offers CBC-mode ciphers
   - **RSA key too short** (512-bit default on old IOS) — OpenSSH 10.3+ rejects with "Invalid key length"

3. **Client-side workaround** (temporary, for immediate access):
   ```bash
   ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 \
       -oHostKeyAlgorithms=+ssh-rsa \
       -oCiphers=+aes128-cbc \
       -oMACs=+hmac-sha1 \
       -o StrictHostKeyChecking=no \
       a.alavi@<switch-ip>
   ```

4. **Permanent fix** (regenerate 2048-bit RSA key via Telnet):
   - Connect via telnet
   - Enter enable/config mode
   - **IOS 12.2 syntax:** `crypto key generate rsa general-keys modulus 2048`
   - **IOS 15.x syntax:** `crypto key generate rsa modulus 2048`
   - Answer `yes` to replacement prompt
   - Wait 30-90 seconds for generation
   - `write memory` to save
   - If the key still shows as short, `crypto key zeroize rsa <keyname>` first, then generate fresh

5. **Verification:**
   ```bash
   show ip ssh
   show crypto key mypubkey rsa | include Key name
   ```

### Device-Specific Command Lists

**Fortigate:**
```
show system status | show system interface | show system dns | show system ntp
show system ha | show router static | show router info routing-table all
show firewall address | show firewall addrgrp | show firewall policy
show system admin | diagnose sys top-summary
diagnose hardware sysinfo memory | diagnose hardware sysinfo disk
show full-configuration
```

**FortiGate REST API alternative:** For read-only queries (DHCP leases, interface list, firewall policies) the REST API at `/api/v2/monitor/` may be faster than SSH. See `references/fortigate-api-access.md` for login flow, cookie handling, and endpoint reference.

**Cisco Switch:**
```
show version | show running-config | show interfaces | show vlan brief
show spanning-tree | show cdp neighbors | show mac address-table
show interfaces trunk | show etherchannel summary | show ip interface brief
show inventory | show env all | show processes cpu | show memory statistics
show ip ssh | show crypto key mypubkey rsa | show ssh
```

**ESXi — Basic Config Collection:**\n```\nuname -a | vmware -v | esxcli system version get | esxcli hardware platform get\nesxcli system hostname get | esxcli network ip interface list\nesxcli network ip route ipv4 list | esxcli network vm list\nesxcli storage vmfs extent list | esxcli storage core device list\nesxcli system syslog config get | esxcli network firewall ruleset list\n```\n\n**ESXi — Security & Configuration Audit:**\n```\n# Version & patch level\nvmware -v\nesxcli system version get\n\n# SSH & shell config\nvim-cmd hostsvc/advopt/view UserVars.ESXiShellInteractiveTimeOut\nvim-cmd hostsvc/advopt/view UserVars.ESXiShellTimeOut\nvim-cmd hostsvc/advopt/view UserVars.SuppressShellWarning\ncat /etc/ssh/sshd_config | grep -E 'PermitRootLogin|PasswordAuthentication'\n\n# Firewall rules (which services are exposed)\nesxcli network firewall ruleset list\n\n# User accounts & permissions\nesxcli system account list\nesxcli system permission list\n\n# Network exposure details\nesxcli network ip interface list\nesxcli network ip route ipv4 list\n\n# Certificate info\nopenssl x509 -in /etc/vmware/ssl/rui.crt -text -noout | grep -E 'Subject:|Issuer:|Not Before|Not After'\n\n# SNMP status\nesxcli system snmp get | grep -E 'Enable|Communities|Targets|Port'\n\n# Syslog configuration\nesxcli system syslog config get\n\n# NTP\ncat /etc/ntp.conf 2>/dev/null\n\n# DNS\nesxcli network ip dns server list\n\n# VM kernel logs (errors/warnings)\ntail -50 /var/log/vmkernel.log | grep -iE 'error|warn|fail|timeout|scsi|admission'\n```\n\n**ESXi — RAM Analysis (from Windows without sshpass):**\nWhen the client is Windows git-bash (no sshpass), use execute_code with paramiko:\n```python\nimport paramiko, re\nclient = paramiko.SSHClient()\nclient.set_missing_host_key_policy(paramiko.AutoAddPolicy())\nclient.connect(host, username=user, password=pwd, look_for_keys=False, timeout=10)\n\n# Physical memory total\nstdin, stdout, stderr = client.exec_command(\"esxcli hardware memory get\")\n\n# Per-VM allocation from vim-cmd\nstdin, stdout, stderr = client.exec_command(\"vim-cmd vmsvc/getallvms\")\nfor line in lines[1:]:\n    vmid, name = parts[0], parts[1]\n    stdin, stdout, stderr = client.exec_command(f\"vim-cmd vmsvc/get.summary {vmid}\")\n    # Parse memorySizeMB (allocated), guestMemoryUsage (actual), powerState\n```\n| Source | Command | Field | Unit |\n|--------|---------|-------|------|\n| Host total | esxcli hardware memory get | Physical Memory: | Bytes |\n| VM config | vim-cmd vmsvc/get.summary | memorySizeMB | MB |\n| VM actual | vim-cmd vmsvc/get.summary | guestMemoryUsage | MB |\n| VM state | vim-cmd vmsvc/power.getstate | (last line) | string |\n\n**RAM bottleneck heuristic:**| Condition| Verdict|\n| Overcommit > 100% AND actual > 90% of physical | CRITICAL |\n| Overcommit > 100% but actual < 50% | OK — normal overprovisioning |\n| Overcommit < 100% | No bottleneck |\nAlways check guestMemoryUsage (actual guest RAM use), not memorySizeMB (allocation). Real utilization often 5-15%.\n\n**ESXi — Storage & VM Provisioning Audit:**\n```\n# Datastore overview\ndf -h\n\n# Datastore capacity & free space\nvim-cmd hostsvc/datastore/summary <datastore-name>\n\n# All VM power states\nfor vmid in $(vim-cmd vmsvc/getallvms | tail -n +2 | awk '{print $1}'); do\n    name=$(vim-cmd vmsvc/get.summary $vmid | grep 'name = ' | sed 's/.*\"\\(.*\\)\".*/\\1/')\n    state=$(vim-cmd vmsvc/power.getstate $vmid | tail -1 | xargs)\n    printf \"%3s | %-35s | %-12s\\n\" \"$vmid\" \"$name\" \"$state\"\ndone\n\n# Check provisioning type (read VMDK descriptor)\nhead -15 /vmfs/volumes/<datastore>/<vm>/<disk>.vmdk | grep -E 'createType|ddb.thinProvisioned'\n# 'createType=\"vmfs\"' without thinProvisioned = thick lazy zeroed\n# 'ddb.thinProvisioned = \"1\"' = thin\n\n# Flat VMDK sizes (actual allocated space)\nls -lh /vmfs/volumes/<datastore>/*/*-flat.vmdk | awk '{print $5, $NF}'\n\n# VMDK descriptor files (provisioning type for each disk)\nfor f in /vmfs/volumes/<datastore>/*/*.vmdk; do\n    size=$(stat -c%s \"$f\" 2>/dev/null)\n    [ \"$size\" -lt 10000 ] 2>/dev/null && head -15 \"$f\" | grep -E 'createType|thinProvisioned'\ndone\n\n# Snapshot check\nfor vmid in $(vim-cmd vmsvc/getallvms | tail -n +2 | awk '{print $1}'); do\n    snaps=$(vim-cmd vmsvc/get.snapshotinfo $vmid 2>/dev/null | grep -c 'snapshot')\n    [ \"$snaps\" -gt 0 ] 2>/dev/null && echo \"VM $vmid has snapshots\"\ndone\n\n# Orphaned VMDKs (not referenced by any registered VM)\nfind /vmfs/volumes -name '*.vmx' | while read vmx; do\n    grep -q \"$vmx\" /etc/vmware/hostd/vmInventory.xml 2>/dev/null || echo \"UNREGISTERED: $vmx\"\ndone\n\n# Swap file overhead\nls -lh /vmfs/volumes/<datastore>/*/*.vswp 2>/dev/null | awk '{print $5, $NF}'\n```

**Linux Backup Server:**
```
uname -a | cat /etc/os-release | hostnamectl | df -h | lsblk | mount
ip a | ip route | free -h | lscpu | systemctl list-units --type=service --state=running
cat /etc/crontab | ss -tlnp | zpool list
```

**Issabel5 VoIP:**
```
uname -a | cat /etc/os-release | hostnamectl | df -h | free -h | ip a | ip route
asterisk -rx "core show version" | asterisk -rx "core show channels"
asterisk -rx "sip show peers" | asterisk -rx "core show calls"
cat /etc/asterisk/sip.conf | cat /etc/asterisk/extensions.conf
systemctl list-units --type=service --state=running
```

**Veeam Windows (WinRM):**
- Port map: 9392 (Veeam Backup & Replication web UI), 9401 (catalog service), 5985 (WinRM), 3389 (RDP)
- Credentials: Veeam often uses a dedicated local user (e.g. `rescue`) rather than `administrator` — check both
- Commands:
```powershell
Get-ComputerInfo | Select-Object WindowsVersion, OsName, OsVersion, CsName
Get-CimInstance Win32_OperatingSystem
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3"
Get-NetIPAddress -AddressFamily IPv4
Get-Service | Where-Object { $_.Status -eq "Running" }
Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*
Get-Service | Where-Object { $_.Name -match "Veeam|VBR" }
Get-WinEvent -LogName System -MaxEvents 20
```

## Pitfalls

- **ESXi 6.7 EOL:** ESXi 6.7 went end-of-general-support Nov 2022. SSH client will show "WARNING: connection is not using a post-quantum key exchange algorithm" when connecting to 6.7 from modern OpenSSH — this is an upgrade signal, not a misconfiguration.
- **ESXi `vim-cmd` output parsing:** `get.summary` and `get.snapshotinfo` produce vim reflection objects, not flat text. Grepping for `'name = '` works but can also match `hostname`, `displayName`, etc. — pipe through `tail -1` or anchor with `'name = \"'` for reliability.
- **ESXi flat VMDK vs descriptor:** The `.vmdk` file comes in two forms — a small text descriptor (a few hundred bytes) and a large `-flat.vmdk` binary (the actual disk). Reading the descriptor tells you provisioning type; listing the flat file tells you actual allocated space. Use `stat -c%s` on the descriptor to distinguish them (< 10KB = descriptor).
- **Cisco IOS 12.2 RSA key generation:** Requires `general-keys` keyword: `crypto key generate rsa general-keys modulus 2048`. Plain `crypto key generate rsa modulus 2048` gives "Invalid input".
- **Key zeroization:** `crypto key zeroize rsa` removes the SSH key entirely — SSH server stops accepting connections until a new key is generated. Only use when regeneration fails.
- **--More-- pagination:** Always send `terminal length 0` first. Without it, long outputs will paginate and the collector will get stuck.
- **Telnet IAC bytes:** Raw telnet data contains IAC negotiation bytes that must be filtered from the display output. The switch (0xFF) sequences interfere with text parsing.
- **WinRM protocol:** Older Windows servers may not have WinRM over HTTPS enabled. Try HTTP first. NTLM auth over HTTP is more compatible than Kerberos.
- **Paramiko 5.0:** Removed `diffie-hellman-group1-sha1` entirely — cannot be re-enabled. Use the `ssh` CLI tool for legacy Cisco SSH access.
- **OpenSSH 10.3:** Removed `diffie-hellman-group1-sha1` from default KEX list even with `+` prefix — the DH group is too small (768-bit). Only fix is regenerating the switch RSA key to 2048-bit so the KEX reply is accepted.
- **Password authentication via subprocess:** SSH doesn't read passwords from stdin by default (uses `/dev/tty`). Use `sshpass`, `pexpect`, or run from an interactive terminal. On git-bash/Windows, `sshpass` is not readily available — use `execute_code` with `paramiko.SSHClient()` for password-based SSH, or the terminal tool with `pty=True` for interactive SSH.
- **WinRM path encoding bug:** When `pywinrm` sends PowerShell commands containing `_x` in file paths (e.g. `Microsoft.ScreenSketch_11.2307.52.0_x64__8wekyb3d8bbwe`), the `_x` sequence gets XML-escaped to `_x005F_` (Unicode escape for underscore). This causes `Add-AppxPackage -Register` to fail with "Cannot find path". 
  - **Workaround 1:** Pass the path through an environment variable: `$env:PATH_VAR = '...'; Add-AppxPackage -Register "$env:PATH_VAR\AppxManifest.xml"`
  - **Workaround 2:** Use `sess.run_cmd()` (cmd.exe) instead of `sess.run_ps()` for path-sensitive operations
- **AppX deployment in WinRM sessions:** In non-interactive WinRM sessions, `Add-AppxPackage -Register` succeeds (Status: Ok) but `PackageUserInformation` remains empty `{}`. The package registers at system level but **never deploys to the user profile**. The user must log out/in, or the registration must run via a scheduled task with `-LogonType Interactive` for it to populate. Diagnostic commands:
  ```powershell
  Get-AppxPackage -Name <package> | Select-Object Status, PackageUserInformation
  ```

### WinRM: Printer Driver Repair

When a printer shows in the list but jobs sit in the queue with "Printing, Retained":

1. Check PrintService/Admin event log for error **365** (print processor DLL not loading)
2. Error 126 = `ERROR_MOD_NOT_FOUND` — the print processor DLL is missing from the driver folder
3. Source the missing DLL from the manufacturer's driver package
4. Copy to `C:\Windows\System32\spool\DRIVERS\x64\3\` AND `C:\Windows\System32\spool\prtprocs\x64\`
5. Restart the spooler: `Stop-Service Spooler; Start-Service Spooler`
6. Verify with `Get-PrintJob` — queue should empty

For file transfer when SMB is unavailable (different subnets, credential mismatch):
- Start a temporary Python HTTP server on your machine: `python -m http.server 18080 --bind <your-ip>`
- Download via WinRM: `(New-Object Net.WebClient).DownloadFile(url, dest)`
- See `references/winrm-troubleshooting.md` for full details

## Related Files

- `references/cisco-ssh-legacy.md` — detailed SSH algorithm compatibility and fix recipes
- `references/winrm-troubleshooting.md` — WinRM path encoding bug, AppX deployment limitations, pywinrm quirks, printer driver repair, file transfer via HTTP
- `references/esxi-audit-and-optimization.md` — comprehensive ESXi security audit checklist, storage provisioning analysis, thick-to-thin conversion strategies, and Veeam restore tips
- `references/vmware-networking-debug.md` — ESXi port group security investigation for bridge forwarding issues (MAC mismatch, vSwitch policy, packet tracing through vSwitch ports)
- `references/windows-gpu-diagnostics.md` — remote GPU diagnostic workflow using pywinrm, nvidia-smi, WMI, event logs, and powercfg; HVCI/Memory Integrity analysis; PCIe ASPM troubleshooting; session case study
- `references/fortigate-api-access.md` — FortiGate REST API access via cookie-based auth; DHCP lease query, VLAN discovery, common endpoint patterns (tested on FG100D v6.2.17)\n- `references/fortigate-cli-expect.md` — expect-based SSH scripts for FortiGate CLI config when API writes return 403/timeout\n- `references/k3s-nftables-conflict.md` — case study: `flush ruleset` destroying k3s iptables-nft DNAT rules, pod-to-service connectivity broken, fix procedures and verification checklist
- `scripts/winrm-printer-diag.py` — reusable remote printer diagnosis script (checks status, queue, event logs, driver files)\n- `scripts/esxi-memory-probe.py` — reusable ESXi memory bottleneck probe (connects via paramiko, per-VM allocated vs actual RAM, prints verdict)

## Verification Checklist

- [ ] All devices respond to ping
- [ ] Telnet/SSH login succeeds
- [ ] `terminal length 0` sent (Cisco only)
- [ ] Configs save to backup directory
- [ ] SSH to each switch works after key regeneration
- [ ] Documentation generated includes all key findings (versions, interfaces, routes, policies)
- [ ] ESXi version/patch level checked against known EOL dates
- [ ] ESXi SSH, CIM, SNMP, HTTP exposure flagged if inappropriate
- [ ] ESXi all-VM power states captured (look for stale powered-off VMs)
- [ ] ESXi disk provisioning type verified (thick vs thin — flag thick for potential savings)
- [ ] ESXi orphan/abandoned VMX files identified
- [ ] ESXi syslog destination configured (or noted as missing)
