# Network Discovery Session: Multi-VLAN Infrastructure Inventory

**Date:** 2026-07-25  
**Scanning host:** Debian 13 at 192.168.13.18  
**Tools:** nmap, ip/route, curl, ARP cache inspection  

## Scenario

Live inventory of a multi-VLAN infrastructure with known subnets from memory,
but needing current status (live/dead), service identification, and unexpected finds.

## Known Subnets from Memory

| VLAN | Subnet | Purpose |
|------|--------|---------|
| FLOOR3 | 192.168.13.0/24 | My VLAN (scanning host here) |
| LAN4 | 192.168.4.0/24 | Servers, VoIP, cameras |
| MGMT | 192.168.2.0/24 | ESXi, management (firewalled off) |

## Step-by-Step

### 1. Own Position Check
```bash
hostname && ip addr show | grep -E 'inet ' | grep -v 127.0.0.1
ip route
cat /etc/resolv.conf
ip neigh  # ARP cache
```
- Host: `Agent` at 192.168.13.18/24
- Gateway: 192.168.13.4 (Fortinet MAC via ARP)
- DNS: 192.168.13.4
- **ARP cache gold:** found 7 hosts on FLOOR3 including a VMware VM (00:0c:29) at .43, an ASUS at .41, HP at .45, and unidentifed hosts at .47 and .101 — even though some were no longer pingable

### 2. Routing Check
```bash
ip route get 192.168.13.4     # → local subnet
ip route get 192.168.4.1      # → via 192.168.13.4 (reachable)
ip route get 192.168.2.1      # → via 192.168.13.4 (reachable in theory)
```
Result: LAN4 and MGMT route through the FortiGate gateway.

### 3. Install nmap (if missing)
```bash
sudo apt-get update -qq && sudo apt-get install -y -qq nmap
```

### 4. Subnet Sweeps
```bash
nmap -sn -T5 192.168.13.0/24   # FLOOR3
nmap -sn -T5 192.168.4.0/24    # LAN4 (routed)
nmap -sn -T5 192.168.2.0/24    # MGMT — returned nothing (firewalled)
```

**Results:**
- **FLOOR3:** 3 hosts alive (.1 Cisco, .4 FortiGate, .18 me). Many ARP-discovered hosts offline.
- **LAN4:** 18 hosts alive — sparse compared to known inventory
- **MGMT:** 0 hosts — completely blocked. ESXi (expected at .10) unreachable.

### 5. Port Scan & Service Identification
```bash
nmap -sT -F --open -T4 <ip>        # fast scan
nmap -sV -T4 -p<ports> <ip>        # version detection
```

| IP | Ports Found | Identity |
|----|-------------|----------|
| 192.168.13.1 | 22, 23, 80, 443 | Cisco switch (IOS) |
| 192.168.13.4 | 22, 53, 80, 443 | FortiGate (Fortinet MAC) |
| 192.168.4.4 | 22, 53, 80, 443 | FortiGate (other interface) |
| 192.168.4.40 | 80+135+139+445+3389+5985+1801+7070 | Windows Server (IIS 10.0) |
| 192.168.4.41 | 135+139+445+3389+5985+9050 | Windows Server |
| 192.168.4.60 | 80+3389+2000+5060+5357 | Parghar-app (redirects to /fonix/) |
| 192.168.4.71 | 23+80+2000+5060 | VoIP gateway |
| 192.168.4.100 | 135+139+445+3389+2000+5060+5357 | File Server (Windows) |
| 192.168.4.101-108 | 22+2000+5060 | Cisco IP Phones (×8) |
| 192.168.4.110 | 80+443+554+2000+5060 | IP Camera (RTSP) |
| 192.168.4.114 | 80+443+554+2000+5060 | IP Camera (RTSP) |
| 192.168.4.120 | 22+80+443 (Go net/http) | Debian 13 Linux server |
| 192.168.4.200 | 21+80+443+515+631+9100 | Network printer |
| 192.168.4.254 | 22+80+443+2000+5060 | LAN4 gateway/router |

### 6. HTTP Fingerprinting
Used curl to probe web services:
```bash
curl -sI --max-time 5 http://<ip>/ | head -10
curl -s --max-time 5 http://<ip>/ | head -20
```
- .60 → `<title>Document Moved</title>` redirects to `/fonix/Mailbox/#/incomemessage/` → **Barid Fonix** confirmed
- .40 → `<title>IIS Windows Server</title>` with blue ASP.NET placeholder → Windows Server IIS 10.0
- .4 → FortiGate redirect to `/ng`
- .120 → Go net/http server (unknown app)

### 7. Cross-Reference Against Known Memory
- FortiGate FG100D @ .4 → ✅ confirmed
- Parghar-app @ .60 → ✅ confirmed (Barid Fonix)
- File server @ .100 → ✅ confirmed (Windows, SMB)
- DESKTOP-LBK5HFN @ .44 → 🔴 offline / powered off
- ESXi @ .2.10 → 🔴 unreachable (MGMT VLAN firewalled)
- Parghar-db @ .61 → 🔴 expected but not alive (not in nmap results; possibly on .40 or .41)
- Unexpected finds: .40, .41 (two Windows Servers, not in memory), .120 (Debian 13, not in memory), .71 (VoIP gateway)

### 8. ARP Cache Did Double Duty
The ARP cache revealed hosts that nmap ping sweeps missed because they were offline but had recent activity:
- 192.168.13.43 (VMware MAC) → a guest VM that had been running
- 192.168.13.41 (ASUS) → likely a desktop
- 192.168.13.45 (HP) → possibly a printer or workstation
- 192.168.13.47 and .101 → unknown devices

These were all STALE — not currently alive — but their existence was notable.

## Key Takeaways

1. **Always start with `ip neigh`** — it's faster than any scan and catches hosts that block ICMP or are currently offline but were alive recently.
2. **Run `ip route get` per target subnet** — you need to know if you can actually reach a network before burning time on cross-VLAN scans.
3. **Use `-sn` for sweep, `-F --open` for port scan, `-sV` for version** — tiered approach avoids wasting time on slow version detection against every host.
4. **Probe HTTP on any host with port 80/443** — the server header and first page content identify the device faster than any port combination.
5. **Don't trust MAC from routed subnets** — nmap shows the *gateway's* MAC, not the target's, when scanning across VLANs.
6. **Some subnets are intentionally blocked** — the MGMT VLAN gave 0 results even though ESXi is known there. Report "unreachable" rather than "empty" when you know a host should exist.
