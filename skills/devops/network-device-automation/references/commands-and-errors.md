# Network Device Automation — Reference

## Cisco IOS Version Detection
```
show version | include "Cisco IOS Software"
```
- **12.2(55)SE3**: Catalyst 2960S, uses `general-keys` syntax for RSA key gen
- **15.0(2)SE11**: Catalyst 2960S, both syntaxes work
- **15.2(2)E9 / 15.2(4)E10**: Catalyst 2960S / 3750E, both syntaxes work, supports CTR ciphers

## SSH Key Size — DER Parsing Heuristic

When `show crypto key mypubkey rsa` shows hex data, the key size can be estimated:

```
307C300D... = SEQUENCE of 0x7C (124) bytes → ~512-bit
30819F30... = SEQUENCE of 0x9F (159) bytes → ~1024-bit
30820122... = SEQUENCE of 0x0122 (290) bytes → ~2048-bit
```

Quick method: count the hex digit pairs. If the `Key Data:` block is roughly:
- 1 line of output → 512-bit (reject by OpenSSH 10.3)
- 2-3 lines → 768-1024 bit
- 4+ lines → 2048-bit (accepted)

## SSH Algorithm Negotiation Errors

| Error | Meaning | Fix |
|-------|---------|-----|
| `no matching key exchange method found. Their offer: diffie-hellman-group1-sha1` | KEX not in client's allowed list | `-oKexAlgorithms=+diffie-hellman-group1-sha1` |
| `no matching host key type found. Their offer: ssh-rsa` | RSA host key algorithm disabled | `-oHostKeyAlgorithms=+ssh-rsa` |
| `no matching cipher found. Their offer: aes128-cbc,...` | Only CBC ciphers offered | `-oCiphers=+aes128-cbc` |
| `no matching MAC found. Their offer: hmac-sha1,...` | Only SHA-1 MACs offered | `-oMACs=+hmac-sha1` |
| `Invalid key length` | RSA host key < 1024 bits | Regenerate key: `crypto key generate rsa general-keys modulus 2048` |

## Telnet IAC Byte Reference

| Byte | Name | Meaning |
|------|------|---------|
| `0xFF` | IAC | Interpret as command |
| `0xFB` | WILL | Sender wants to enable option |
| `0xFC` | WONT | Sender refuses to enable option |
| `0xFD` | DO | Sender wants receiver to enable |
| `0xFE` | DONT | Sender wants receiver to disable |
| `0xF0` | SE | End of subnegotiation |
| `0xFA` | SB | Subnegotiation begin |

The filter pattern: respond WILL/WONT to any DO/WILL with the corresponding refusal (WONT/DONT) to disable all negotiation. This avoids terminal-type negotiation that would consume input bandwidth.

## Cisco Switch Inventory Commands

```text
show version              → IOS version, uptime, image file, model
show running-config       → full running configuration
show interfaces           → all interface status + counters
show vlan brief           → VLAN assignments
show spanning-tree        → STP status per VLAN
show cdp neighbors        → directly connected devices
show mac address-table    → MAC forwarding table
show interfaces trunk     → trunk ports and allowed VLANs
show etherchannel summary → port-channel members
show ip interface brief   → IP address per interface
show inventory            → hardware serial numbers
show env all              → power supply, fan, temp status
show processes cpu        → CPU utilization
show memory statistics    → memory utilization
show ip ssh               → SSH server config + algorithms
show crypto key mypubkey rsa → RSA public keys
show ssh                  → active SSH sessions
```

## Fortigate Useful Commands

```text
show system status
get system performance status
show system interface
show system dns
show system ntp
show system ha
show router static
show router info routing-table all
show firewall address
show firewall addrgrp
show firewall policy
show system admin
diagnose sys top-summary
diagnose hardware sysinfo memory
diagnose hardware sysinfo disk
show full-configuration
```

## WinRM Diagnostic Commands

```powershell
# System info
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber
Get-CimInstance Win32_ComputerSystem | Select-Object Model, Manufacturer

# AppX package status
Get-AppxPackage -Name "*ScreenSketch*" -AllUsers | Format-List *
Get-AppxProvisionedPackage -Online | Where-Object DisplayName -Match "ScreenSketch"

# Register package for current user
Add-AppxPackage -Register "C:\Program Files\WindowsApps\Microsoft.ScreenSketch_*\AppxManifest.xml" -DisableDevelopmentMode

# Find executables in WindowsApps
Get-ChildItem "C:\Program Files\WindowsApps" -Recurse -Filter "winget.exe" -ErrorAction SilentlyContinue

# Event logs for a specific app
Get-WinEvent -LogName Application -MaxEvents 100 | Where-Object { $_.Message -match "ScreenSketch|Snipping" }
