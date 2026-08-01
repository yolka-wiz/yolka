---
name: network-config-backup
description: >
  Collect read-only configuration backups from network infrastructure
  devices (firewalls, switches, servers, VoIP, Windows) via SSH, Telnet,
  and WinRM. Supports CSV-driven inventory, structured backup directories,
  and Markdown documentation generation.
trigger:
  - User provides a CSV/XLSX inventory of network devices with IPs and credentials
  - "Take backup of all network devices"
  - "Create documentation from device configs"
  - "We need to document the network infrastructure"
  - "Backup configs from [firewall | switch | server]"
tags: [network, backup, config, ssh, telnet, winrm, documentation]
---

# Network Configuration Backup & Documentation

Read-only collection of running configs from heterogeneous network infrastructure.  
**No changes are made to any device.**

## Workflow

### 1. Inventory → scripts

Parse the inventory CSV. For N devices you'll need one collector approach per protocol:

```python
devices = [
    {'name': 'Fortigate', 'host': '10.0.0.1', 'protocol': 'ssh', 'username': 'admin', 'password': '...'},
    {'name': 'Cisco-SW1',  'host': '10.0.0.2', 'protocol': 'telnet', ...},
    {'name': 'Veeam',      'host': '10.0.0.3', 'protocol': 'winrm', ...},
]
```

### 2. Pick the right collection method per protocol

#### SSH — Linux/ESXi servers → `exec_command`

```python
import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, password=pwd, timeout=30)
for cmd in commands:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace')
```
Best for: ESXi, Ubuntu/Debian/RHEL, Issabel, any standard Linux shell.

#### SSH — Network devices (Fortigate, IOS, NX-OS) → `invoke_shell`

Network device CLIs are interactive and don't work with `exec_command`.  
Use `invoke_shell` + a **bounded read loop** (never an unbounded `while True: recv()`):

```python
shell = client.invoke_shell(term='vt100', width=200, height=100)
time.sleep(3)
shell.settimeout(2)

def safe_recv(max_iter=30, per_iter_timeout=2):
    out = b""
    for _ in range(max_iter):
        try:
            chunk = shell.recv(65535)
            if not chunk: break
            out += chunk
        except socket.timeout:
            break
    return out.decode('utf-8', errors='replace')

# Drain initial banner
safe_recv(50, 1)

for cmd in commands:
    shell.send(cmd + "\n")
    time.sleep(2)
    result = safe_recv(30, 3)
    # save result
```

**Pitfall:** The Fortigate shell prompt like `FortiRad $` won't match simple `$` patterns — don't rely on prompt detection; use bounded time-based reads.

#### Telnet — Cisco IOS switches → raw sockets + IAC stripping

```python
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
sock.connect((host, 23))

# Must strip Telnet IAC negotiation bytes from output
IAC = bytes([255]); DONT = bytes([254]); DO = bytes([253])
WONT = bytes([252]); WILL = bytes([251]); SE = bytes([240])

def recv_clean(timeout=5):
    data = b""
    sock.settimeout(timeout)
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk: break
            data += chunk
    except socket.timeout: pass
    # Filter IAC sequences
    filtered = b""; i = 0
    while i < len(data):
        if data[i:i+1] == IAC:
            if i+1 < len(data):
                cmd = data[i+1:i+2]
                if cmd in [DO,DONT,WILL,WONT] and i+2 < len(data):
                    opt = data[i+2:i+3]
                    if cmd == DO: sock.send(IAC + WONT + opt)
                    elif cmd == WILL: sock.send(IAC + DONT + opt)
                    # (DONT/WONT responses suppress negotiation)
                    i += 3; continue
                elif cmd == SB:  # subnegotiation
                    end = data.find(IAC + SE, i)
                    if end != -1: i = end + 2; continue
                    else: break
                elif cmd == SE: i += 2; continue
                else: i += 2; continue
            else: break
        else:
            filtered += data[i:i+1]; i += 1
    return filtered.decode('utf-8', errors='replace')
```

**Key step — disable paging immediately after login:**
```python
sock.send(b"terminal length 0\r\n")
```
This prevents `--More--` prompts from blocking output collection.

**Login sequence** for Cisco IOS (typical):
```
"User Access Verification\r\nUsername: " → send username
"Password: " → send password  
"hostname#" → we're in privileged EXEC mode
```
Many Cisco switches drop directly into `#` (privileged) mode after login with an admin account.

#### WinRM — Windows servers → pywinrm with NTLM auth

```python
import winrm

for proto, port in [('http', 5985), ('https', 5986)]:
    try:
        s = f"{proto}://{host}:{port}/wsman"
        sess = winrm.Session(s, auth=(username, password), transport='ntlm')
        r = sess.run_ps(powershell_command)
        if r.status_code == 0:
            out = r.std_out.decode('utf-8', errors='replace')
            break
    except Exception:
        continue  # try next protocol
```

**Pitfalls:**
- Always try HTTP:5985 **first** — many Windows servers don't have WinRM HTTPS configured
- `Get-WindowsFeature` can **hang** indefinitely — avoid it or set a hard timeout
- `Get-Module -ListAvailable` with many modules is very slow — use filtered queries instead
- Save output progressively (after each command) so a hung command doesn't lose prior data

### 3. Organize backup files

```
~/Documents/backup/
├── fortigate/
├── esxi/
├── cisco-switches/
├── backup-storage/
├── issabel/
└── veeam/
```

Save each device as `<device-name>.txt` with a header block containing device name, IP, and timestamp.

### 4. Generate documentation

After collecting all configs, build a Markdown document summarizing:
- Device model, version, hostname, uptime
- Interface IPs and VLANs
- Firewall/routing policy counts
- Running services
- Storage (datastores, disks)
- VM inventory
- Credentials reference table
- File manifest

Use `extract_between(text, "COMMAND: show X", "COMMAND:")` to pull individual command outputs from the saved files.

## Useful commands per device type

### Cisco IOS
```
show version
show running-config
show interfaces
show vlan brief
show spanning-tree
show cdp neighbors
show mac address-table
show interfaces trunk
show etherchannel summary
show ip interface brief
show inventory
show env all
show processes cpu
show memory statistics
```

### Cisco IOS — SSH diagnostics

Use these (via Telnet) to diagnose SSH failures when modern clients cannot connect:

```
show ip ssh                          # Shows enabled version, auth methods, cipher/MAC/KEX lists
show crypto key mypubkey rsa         # Shows RSA key size (hex decode to determine bit length)
show ssh                             # Shows active SSH sessions
```

**RSA key size from hex:** In `show crypto key mypubkey rsa` output, the hex data starts with a DER tag:
- `307C` = 512-bit key (rejected by OpenSSH 10.3+ as too short)
- `3081` = 1024-bit key (minimum for modern clients)
- `3082` = 2048-bit key (recommended)

**See `references/cisco-ssh-troubleshooting.md`** for the full diagnostic chain.

### Fortigate
```
show system status
get system performance status
show system interface
show system dns
show system ntp
show system ha
show router static
show firewall address
show firewall addrgrp
show firewall policy
show system admin
diagnose sys top-summary
diagnose hardware sysinfo memory
diagnose hardware sysinfo disk
```

### ESXi
```bash
esxcli system version get
esxcli hardware platform get
esxcli system hostname get
esxcli network ip interface list
esxcli network ip route ipv4 list
esxcli network vm list
esxcli storage vmfs extent list
esxcli storage core device list
esxcli system syslog config get
```

### Linux server
```bash
cat /etc/os-release
hostnamectl
df -h
lsblk
mount
cat /etc/fstab
ip a
ip route
free -h
systemctl list-units --type=service --state=running
ss -tlnp
```

### Veeam/Windows (via WinRM PowerShell)
```powershell
Get-ComputerInfo | Select-Object OsName, OsVersion, CsName, CsTotalPhysicalMemory | Format-List
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID, @{N="SizeGB";E={[math]::Round($_.Size/1GB,2)}}
Get-Service | Where-Object { $_.Status -eq "Running" } | Select-Object Name, DisplayName, StartType
Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" | Where-Object { $_.DisplayName -match "Veeam|Backup" }
Get-Service | Where-Object { $_.Name -match "Veeam|VBR" }
Add-PSSnapin VeeamPSSnapIn; Get-VBRJob
Get-SmbShare
```

## Troubleshooting: Cisco SSH failures with modern clients

When `ip ssh version 2` is configured but SSH fails with errors like `"no matching key exchange method"`, `"no matching cipher"`, or `"Invalid key length"`, the root cause is deprecated algorithms in modern clients (OpenSSH >= 8.8, Paramiko >= 3.x).

### Diagnostic chain (via Telnet)

| Error | Likely cause | Verification |
|-------|-------------|-------------|
| `no matching key exchange method found` | Only `diffie-hellman-group1-sha1` offered — removed from OpenSSH 10.3 and Paramiko 5.0 | `show ip ssh` shows no KEX list |
| `no matching host key type found. Their offer: ssh-rsa` | `ssh-rsa` host key algorithm disabled since OpenSSH 8.8 | `show crypto key mypubkey rsa` confirms RSA key |
| `no matching cipher found. Their offer: aes128-cbc,...` | Only CBC ciphers offered — disabled in modern clients | `show ip ssh` shows cipher list on IOS 15.x |
| `Invalid key length` | RSA host key is only 512-bit (< 1024 minimum) | Decode DER hex: `307C`=512, `3081`=1024, `3082`=2048 |

### Why this happens

Old Cisco IOS (12.2, 15.0, early 15.2) on Catalyst 2960S/3750E:
1. Default `crypto key generate rsa` without modulus creates **512-bit RSA keys**
2. Only offer `diffie-hellman-group1-sha1` key exchange
3. Only offer CBC-mode ciphers
4. Only offer `ssh-rsa` host key algorithm

OpenSSH 10.3 and Paramiko 5.0 have removed or disabled all of these.

### Fix options

**A) Fix on the switch (IOS 15.x+)** — regenerate RSA key and add modern KEX:
```cisco
conf t
crypto key generate rsa modulus 2048
ip ssh server algorithm kex diffie-hellman-group14-sha1
ip ssh server algorithm kex diffie-hellman-group-exchange-sha256
end
```
Works on IOS 15.2(4)E10 (Catalyst 3750E). May work on 15.0(2)SE11. Does NOT work on 12.2(55)SE3 (no KEX config support).

**B) Use an older client** — PuTTY still supports legacy algorithms.

**C) Continue using Telnet** — `transport input all` is already configured.

### Reference

See `references/cisco-ssh-troubleshooting.md` for full command-by-command transcript and ASN.1 key-size decoding.

## Pitfalls

| Pitfall | Solution |
|---------|----------|
| Fortigate/network-device SSH hangs with `exec_command` | Use `invoke_shell()` + bounded `recv()` loops |
| Cisco telnet output garbled with extra bytes | Strip IAC (255) negotiation sequences |
| `--More--` pagination blocks command output | Send `terminal length 0` immediately after login |
| WinRM `Get-WindowsFeature` hangs | Skip that cmdlet; use `Get-CimInstance Win32_ServerFeature` if needed |
| PowerShel `$_` and `$` in pywinrm strings | Use single-quoted Python strings for the PS command |
| Python 3.12+ f-string | No backslash in f-string expression parts — pre-compute into a variable |
| WinRM HTTPS connection refused | Fall back to HTTP:5985 |
| Large `show running-config` output | Ensure `terminal length 0` is set first; save progressively |
| pywinrm command times out on long PS queries | Keep PS commands focused (filtered, truncated output) |

## Python version note

Python 3.12+ does **not** allow backslash characters inside f-string expression parts.  
Instead of: `f"{l.strip('\"')}"`  
Write: `v = l.strip('"'); f"{v}"`

## Verification checklist

- [ ] All devices in inventory are accounted for in backup directory
- [ ] Each file has a header with device name, IP, timestamp
- [ ] No error/exception messages at the end of the backup run (partial data is fine but flagged)
- [ ] Documentation includes: version info, IPs, storage, services, policy/routing counts
- [ ] Passwords from original CSV are NOT in the documentation (reference only)
- [ ] Documentation saved to `~/Documents/Network-Infrastructure-Documentation.md`
