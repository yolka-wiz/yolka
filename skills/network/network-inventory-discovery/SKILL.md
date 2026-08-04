---
name: network-inventory-discovery
description: Discover LAN hosts via nmap, ARP, MAC OUI, and fingerprints.
version: 1.0.0
author: Hermes Agent
tags: [network, discovery, inventory, nmap, scanning, fingerprinting]
---

# Network Inventory & Discovery

Map out a live network segment when you have a host on a routed VLAN but no FortiGate/firewall
credentials for DHCP-based discovery. This is **Track B** — the direct-scan complement to the
FortiGate-based approach in `network-device-management` Phase 0.

The output is a structured device inventory (IP, MAC, vendor, open ports, OS/service hints) that
feeds into the config-backup, automation, and device-management skills.

## When to Use

- User asks "what's on the network" or "list your infrastructure"
- You have network access (routed VLAN) but no device credentials yet
- You need a baseline inventory before deciding what to back up or automate
- ARP cache shows stale hosts you want to probe
- You need to identify unknown devices by fingerprint

## Workflow

### 1. Baseline: Know Your Position

Before scanning, understand your own network context:

```bash
# Your interfaces and IPs
ip addr show | grep -E 'inet ' | grep -v 127.0.0.1

# Default gateway and routing
ip route

# DNS resolver
cat /etc/resolv.conf

# ARP cache for recently-active hosts
ip neigh
```

The ARP cache is gold: it shows hosts that have communicated recently but may not respond
to ICMP. Valuable for finding VMs, printers, and devices that block ping.

**Pitfall:** ARP entries go STALE when hosts go offline. A host in `STALE` state is not
currently reachable but was alive recently. A host in `REACHABLE` state is actively talking.

### 2. Subnet Sweep (ICMP)

Use nmap for fast subnet discovery. Be aware of your routing — you may need to scan multiple
subnets reachable via the gateway.

```bash
# Fast ping sweep of a /24 (3-10 seconds)
nmap -sn -T5 192.168.x.0/24
```

Output: list of live hosts with MAC addresses. The `-sn` flag does ping scan only — no port scan.

**Pitfall:** Some hosts block ICMP and won't appear in `-sn` scans. For those, use `-Pn`
(no ping) with port scans — but this is much slower on a full subnet.

**Pitfall:** If nmap is not installed, install it:
```bash
sudo apt-get update -qq && sudo apt-get install -y -qq nmap
```

**MAC addresses from nmap:** The `-sn` scan shows MAC and vendor for local-subnet hosts.
For hosts on other routed subnets, MACs are not returned (the gateway's MAC is the link-layer
hop). Use ARP inspection on the scanning host for local-subnet MACs.

### 3. Route-Aware Subnet Selection

Not all subnets may be reachable. Verify before scanning:

```bash
# Check which subnets route through your gateway
ip route get 192.168.other.1
```

If the route exists, scan it. If there's no route, the subnet is firewalled or on a
physically separate network segment — report it as unreachable rather than scanning blind.

**Pitfall — Distinguish "firewalled" from "empty":** A subnet scan that returns 0 hosts
may mean:
- The entire subnet is firewalled off (no ICMP or TCP allowed) — common for MGMT VLANs
- All hosts are genuinely offline (powered down during off-hours)
- The routing table says it's reachable but the firewall on the gateway silently drops packets

When you know specific hosts should exist (from memory, configs, or inventory), report a
firewalled subnet explicitly: "MGMT 192.168.2.0/24 — 0 hosts detected, likely firewalled"
rather than just "no hosts found". If you have no expectations, note "empty" neutrally.

### 4. Port Scan Live Hosts

Once you know which hosts are alive, do fast port scans for service identification:

```bash
# Fast scan (top 1000 ports, TCP only, open only)
nmap -sT -F --open -T4 <ip>

# Service version detection (slower, more informative)
nmap -sV -T4 -p<ports-of-interest> <ip>
```

**Key port mappings for quick identification:**

| Port(s) | Likely Device |
|----------|---------------|
| 22 (SSH) + 23 (Telnet) + 80/443 (HTTP/S) | Cisco switch or router |
| 22 + 53 + 80/443 | FortiGate or router with DNS |
| 135 + 139 + 445 + 3389 + 5985 | Windows Server |
| 80 (IIS) + 135 + 139 + 445 + 3389 + 5985 | Windows Server with web UI |
| 80/443 + 554 (RTSP) | IP Camera |
| 2000 (SCCP) + 5060 (SIP) | VoIP phone or gateway |
| 21 + 80 + 443 + 515 + 631 + 9100 | Network printer |
| 22 + 80/443 (Go net/http) | Linux server (Debian/Ubuntu) |
| 80 + 443 + 9401 | Veeam backup server |
| 22 (OpenSSH) + 80/443 (Go/IPFS) | Custom Linux service |
| **6443 (kube-apiserver) + 10250 (kubelet)** | **K3s / K8s node** — hit `https://<ip>:6443/`, expect 401 JSON |
| 80/443 (Go net/http, **404 on all paths**) | **Traefik ingress** — bare K3s with no routes configured |
| 30102–30314 (NodePort range) + 6443 | K3s cluster with Traefik LoadBalancer on NodePorts |

**Pitfall:** Some hosts (especially Windows) block ICMP but respond to TCP port scans.
Always follow up ping-sweep misses with `-Pn` scans on individual IPs that you know
exist from ARP cache or memory.

### 5. Accessing Hosts with Password-Based SSH

When discovery yields IPs but only password-based SSH credentials are available (from
a CSV file, password manager, or memory), install `sshpass` for non-interactive auth:

```bash
sudo apt-get install -y sshpass
sshpass -p '<password>' ssh -o StrictHostKeyChecking=no user@target 'command'
```

**Pitfall:** sshpass passes the password as a CLI argument — it will appear in `ps` output
and shell history. For production use, prefer key-based auth. For recon, it's acceptable on
isolated admin networks. Clean up with `history -c` if the flag was used with sensitive creds.

**Pitfall:** Not all servers accept password auth — the remote SSH config may have
`PasswordAuthentication no`. If sshpass fails with "Permission denied (publickey,password)",
the server requires key-based auth. Report this rather than retrying endlessly.

### 6. MAC OUI Vendor Identification

MAC addresses identify the hardware vendor, which helps categorize unknown devices:

```bash
# From nmap's built-in prefix database
grep -i "24:e9:b3" /usr/share/nmap/nmap-mac-prefixes

# Common infrastructure OUIs:
# 00:0c:29 → VMware (virtual machine)
# 90:6c:ac → Fortinet
# 24:e9:b3 → Cisco
# f4:39:09 → HP
# e8:9c:25 → ASUS
# d0:21:f9 → Ubiquiti
```

**Pitfall:** MAC OUI only identifies the NIC vendor, not the device function. A VMware MAC
(00:0c:29) tells you a guest VM exists — the actual OS could be anything.

### 7. HTTP Service Fingerprinting

For hosts with HTTP/HTTPS open, probe the web service to identify the application:

```bash
# Check HTTP headers and redirects
curl -sI --max-time 5 http://<ip>/
# Get first page content
curl -s --max-time 5 http://<ip>/ | head -20
```

**Fingerprint patterns:**

| Server header / content | Likely Device |
|------------------------|---------------|
| `Server: cisco-IOS` | Cisco IOS web config |
| `Location: /ng` or FortiGate redirect | FortiGate firewall |
| `Server: Microsoft-IIS/10.0` | Windows Server web app |
| `Server: Apache` + redirect to `/fonix/` | Barid Fonix (Parghar) |
| `Server: Apache-Coyote` + XML on `:8080` | Veeam REST API |
| `Server: bsa/1.2` + redirect to `index.asp` | Printer web interface |
| `Go-IPFS json-rpc or InfluxDB API` | Go-based service (custom) |

### 8. OS Fingerprinting

If root access is available:

```bash
# OS detection (requires root)
sudo nmap -O -T4 <ip>
```

Without root (non-privileged), infer OS from:
- Service versions: `nmap -sV`
- Open port patterns: Windows has 135/139/445/3389/5985, Linux has 22/53/80/443
- SSH banners: `SSH-2.0-Cisco-1.25` = IOS, `SSH-2.0-OpenSSH_*` = Linux
- HTTP Server headers

**Pitfall:** `nmap -O` without root/sudo returns "requires root privileges". Don't rely on
it in non-root contexts — use the inference methods above instead.

### 9. Cross-Reference Against Known Inventory

After discovering all live hosts, cross-reference against:
1. Previously-saved credentials (in memory or CSV files)
2. Expected infrastructure from past sessions
3. Known MAC-to-device mappings

Flag discrepancies:
- A host that's expected but unreachable → likely offline or moved
- A host that's alive but unexpected → investigate
- A new subnet's hosts → expand network documentation

### 9. Present a Structured View

Organize the results as:

```
Per-subnet:
  IP | MAC (OUI Vendor) | Identity | Open Ports | Status (Up/Offline)

Topology summary:
  (my host) → gateway → scanned subnets

Key findings:
  - Unexpected hosts found
  - Expected hosts missing
  - Credentials available vs needed
```

## Related Files

- `references/network-discovery-session.md` — full session transcript covering subnet scanning, ARP investigation, service fingerprinting, and inventory compilation across multiple VLANs

## Verification Checklist

- [ ] Own IP, routes, and DNS recorded
- [ ] ARP cache inspected for recently-active hosts not responding to ping
- [ ] All reachable subnets scanned (`-sn`)
- [ ] All live hosts port-scanned (`-F --open`)
- [ ] Key hosts' services version-identified (`-sV`)
- [ ] MAC addresses looked up for vendor inference
- [ ] HTTP services probed for application identification
- [ ] Results cross-referenced against known inventory
- [ ] Discrepancies (missing expected hosts, unexpected hosts) flagged
- [ ] Structured inventory presented per subnet
