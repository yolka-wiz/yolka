#!/usr/bin/env python3
"""
ESXi Memory Analysis Probe

Connects to an ESXi host over SSH (password auth), queries per-VM memory 
allocation vs actual usage, and prints a table. Detects RAM bottlenecks.

Usage:
    python3 esxi-memory-probe.py <host> <username> <password>
    
Example:
    python3 esxi-memory-probe.py 192.168.2.10 alavi ESX!8orn@
"""
import paramiko, re, sys, socket

def probe(host, user, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, look_for_keys=False, timeout=10)

    # Host total memory
    stdin, stdout, stderr = client.exec_command("esxcli hardware memory get")
    total_bytes = 0
    for line in stdout.read().decode().split('\n'):
        if 'Physical Memory:' in line:
            m = re.search(r'Physical Memory:\s+(\d+)', line)
            if m: total_bytes = int(m.group(1))
    total_gb = total_bytes / (1024**3)

    # All VMs with IDs
    stdin, stdout, stderr = client.exec_command("vim-cmd vmsvc/getallvms")
    lines = stdout.read().decode().strip().split('\n')
    vms = []
    for line in lines[1:]:
        parts = line.strip().split(None, 6)
        if len(parts) >= 2:
            vms.append((parts[0], parts[1]))

    # Per-VM memory & state
    rows = []
    total_alloc = 0
    total_used = 0
    for vmid, name in vms:
        stdin, stdout, stderr = client.exec_command(f"vim-cmd vmsvc/get.summary {vmid}")
        summary = stdout.read().decode()
        
        alloc_mb = 0
        used_mb = 0
        state = "unknown"
        
        m = re.search(r'memorySizeMB\s*=\s*(\d+)', summary)
        if m: alloc_mb = int(m.group(1))
        m = re.search(r'guestMemoryUsage\s*=\s*(\d+)', summary)
        if m: used_mb = int(m.group(1))
        m = re.search(r'powerState\s*=\s*\"(\w+)\"', summary)
        if m: state = m.group(1)
        
        if alloc_mb > 0:
            rows.append((name, vmid, alloc_mb, used_mb, state))
            total_alloc += alloc_mb
            total_used += used_mb

    client.close()

    # Print report
    print(f"ESXi Host: {host}  ({socket.gethostbyaddr(host)[0] if host != host else host})")
    print(f"{'='*70}")
    print(f"{'VM Name':30s} {'ID':>4s} {'Alloc':>7s} {'(GB)':>6s} {'Used':>7s} {'(GB)':>6s} {'%':>5s} {'State':10s}")
    print(f"{'-'*70}")
    for name, vmid, alloc, used, state in sorted(rows, key=lambda x: -x[2]):
        pct = (used / alloc * 100) if alloc > 0 else 0
        print(f"{name[:30]:30s} {vmid:>4s} {alloc:>5d}M ({alloc/1024:>4.1f}) {used:>5d}M ({used/1024:>4.1f}) {pct:>4.1f}%  {state:10s}")
    
    print(f"{'-'*70}")
    print(f"{'TOTAL':30s} {'':>4s} {total_alloc:>5d}M ({total_alloc/1024:>4.1f}) {total_used:>5d}M ({total_used/1024:>4.1f})")
    print(f"{'Physical RAM':30s} {'':>4s} {total_gb*1024:>5.0f}M ({total_gb:>4.1f})")
    print()
    overcommit = total_alloc / (total_gb * 1024) * 100
    utilization = total_used / (total_gb * 1024) * 100
    print(f"Overcommit ratio: {overcommit:.1f}%")
    print(f"Utilization:      {utilization:.1f}%")
    
    if overcommit > 100 and utilization > 90:
        print("VERDICT: CRITICAL — RAM bottleneck likely")
    elif overcommit > 100 and utilization > 50:
        print("VERDICT: WARNING — elevated memory pressure")
    elif overcommit > 100:
        print("VERDICT: OK — overprovisioned, but real usage low. No bottleneck.")
    else:
        print("VERDICT: No RAM bottleneck.")
    
    # Flag oversized VMs
    for name, vmid, alloc, used, state in sorted(rows, key=lambda x: -x[2]):
        pct = (used / alloc * 100) if alloc > 0 else 0
        if alloc > 8000 and pct < 10 and state == "poweredOn":
            print(f"  NOTE: {name} has {alloc}M allocated but only uses {used}M ({pct:.0f}%)")
    
    if total_alloc > total_gb * 1024:
        print(f"  NOTE: Total allocated ({total_alloc/1024:.1f}G) exceeds physical ({total_gb:.1f}G)")
    
    return rows

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <host> <username> <password>")
        sys.exit(1)
    probe(sys.argv[1], sys.argv[2], sys.argv[3])
