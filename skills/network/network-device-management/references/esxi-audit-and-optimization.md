# ESXi Audit & Storage Optimization Reference

This reference covers the key checks from a comprehensive ESXi host audit and the strategies for reclaiming storage from thick-provisioned VMs. Use alongside the `esxcli` and `vim-cmd` commands in the main SKILL.md.

## Memory Analysis (RAM Bottleneck Check)

### Quick Probe (SSH + paramiko from Windows)

When the client is Windows git-bash (no sshpass), use execute_code with paramiko:

```python
import paramiko, re
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, password=pwd, look_for_keys=False, timeout=10)

# Host total — esxcli hardware memory get
# Per-VM — vim-cmd vmsvc/getallvms -> get.summary {vmid}
# Parse memorySizeMB, guestMemoryUsage, powerState
```

| Source | Command | Key Field | Unit |
|--------|---------|-----------|------|
| Host total | esxcli hardware memory get | Physical Memory: | Bytes |
| VM config | vim-cmd vmsvc/get.summary <vmid> | memorySizeMB | MB |
| VM actual | vim-cmd vmsvc/get.summary <vmid> | guestMemoryUsage | MB |

### Bottleneck Heuristic

| Condition | Verdict |
|-----------|---------|
| Overcommit > 100% AND actual > 90% of physical | CRITICAL |
| Overcommit 100-150% but actual < 50% | OK — normal overprovisioning |
| Overcommit < 100% | No bottleneck |

### Pitfalls

- **vim-cmd is slow** (0.3-0.5s per call on ESXi 6.7). Expect 5-8s for 15 VMs.
- **Parsing fragility** — vim reflection output is key=value lines, not JSON. Anchor name extraction with `'name = \"'`
- **ESXi 6.7 SSH banner warning** — Modern OpenSSH warns about post-quantum key exchange. Cosmetic only.
- **Real utilization** is typically 5-15% of physical even at 114% overcommit. Always check `guestMemoryUsage`, not `memorySizeMB`.

### Reusable Script

```bash
python3 scripts/esxi-memory-probe.py <host> <username> <password>
```

## Security Findings to Check

### 1. ESXi Version / Patch Level
- **ESXi 6.7** went end-of-general-support Nov 15, 2022
- **ESXi 7.0** went end-of-general-support Oct 2024
- **ESXi 8.0** is currently supported
- Check with: `vmware -v` then `esxcli system version get`
- Kernel logs show `WARNING: connection is not using a post-quantum key exchange algorithm` when clients connect to too-old SSH

### 2. SSH Configuration
- **PermitRootLogin** — should be set to `no` or at minimum restrict to key-only (ESXi sets key-only by default in 7.0+)
- **PasswordAuthentication** — should be **no** on ESXi (key-based only)
- **Shell timeout** (`UserVars.ESXiShellTimeOut`) — should be > 0 (in minutes). 0 = never expires, which leaves idle SSH sessions open forever
- **SSH firewall rule** — should be disabled unless actively troubleshooting. Enable via DCUI only when needed
- Check: `/etc/ssh/sshd_config` + `vim-cmd hostsvc/advopt/view UserVars.ESXiShellTimeOut`

### 3. CIM Services (Common Information Model)
- CIMHttpServer (port 5988/TCP), CIMHttpsServer (5989/TCP), CIMSLP (427/TCP+UDP)
- Rarely needed unless hardware monitoring tools are in use
- Check: `esxcli network firewall ruleset list | grep CIM`
- Disable if not used: `esxcli network firewall ruleset set --ruleset-id=CIMHttpServer --enabled=false`

### 4. SNMP
- Often enabled with empty community strings — open but dead
- Check: `esxcli system snmp get | grep -E 'Enable|Communities|Targets'`
- If no monitoring targets configured, disable: `esxcli network firewall ruleset set --ruleset-id=snmp --enabled=false`

### 5. HTTP (port 80) Exposure
- webAccess firewall rule opens inbound TCP 80
- Should be disabled if not needed (all traffic should use HTTPS/443)
- Check: `esxcli network firewall ruleset list | grep webAccess`

### 6. User Accounts & Permissions
- Too many Admin-level users is a risk
- Check: `esxcli system account list` + `esxcli system permission list`
- `vpxuser` is the vCenter agent account — if the host is standalone (no vCenter), this account is stale
- On ESXi 6.7, all non-root users show as "Admin" in the permission list

### 7. Remote Syslog
- Critical for forensics if host crashes
- Check: `esxcli system syslog config get | grep 'Remote Host'`
- Should point to a centralized syslog server; if `<none>`, logs live on scratch partition and are lost on reboot

### 8. Certificate
- ESXi self-signed certificate may be issued to IP address instead of FQDN
- Check: `openssl x509 -in /etc/vmware/ssl/rui.crt -text -noout | grep Subject`
- Reissue via DCUI or Certificate Manager if needed

### 9. Memory Overcommit
- `MemSchedAdmit: Admission failure` in vmkernel.log indicates memory pressure
- Check: `tail /var/log/vmkernel.log | grep -i admission`
- Check swap config: `esxcli sched swap system get`
- Host cache on local disk is better than nothing but SSD/remote swap is preferred

## Storage Provisioning Analysis

### Understanding VMDK Descriptors

| Descriptor | Meaning |
|---|---|
| `createType="vmfs"` | Thick provisioned lazy zeroed (default) — space allocated at creation |
| `createType="vmfs"` + `ddb.thinProvisioned = "1"` | Thin provisioned — space grows with actual usage |
| `createType="vmfs"` + `ddb.thinProvisioned = "0"` | Thick provisioned eager zeroed — space allocated AND zeroed upfront |

**To check a VMDK:**
```bash
head -15 /vmfs/volumes/<ds>/<vm>/<disk>.vmdk | grep -E 'createType|thinProvisioned'
```

**Key caveat:** The descriptor file is the small text file (a few hundred bytes). The actual disk data is in the `-flat.vmdk` file which is many GB. A descriptor with `createType="vmfs"` and no `ddb.thinProvisioned` is **thick lazy zeroed** — the flat file is always the full provisioned size regardless of actual data.

### Common Storage Problems

1. **Multiple copies of the same VM** — Original + "_reduced" VM both exist with full-size disks. Delete the old one after migration is verified.
2. **Powered-off vCenter** — Often left around with many VMDKs (snapshots, old OS disks). Can be 500+ GB wasted.
3. **"New Virtual Machine" orphans** — VMX + VMDK left on datastore that was never registered in inventory.
4. **Swap files (.vswp)** — Each powered-on VM gets a .vswp file equal to the unreserved memory. Check with `ls -lh /vmfs/volumes/<ds>/*/*.vswp`.
5. **Change Tracking files (.ctk.vmdk)** — Veeam/Bacula CBT tracking files. Small but can accumulate.
6. **Snapshot consolidation needed** — If a VM has snapshots, the old -delta.vmdk files and -flat.vmdk coexist, doubling disk usage.

## Thick-to-Thin Conversion Strategies

### Strategy 1: Veeam Backup + Restore as New VM (Safest)
1. Take full VM backup with Veeam
2. Restore to **new location** → in Disk step choose **Thin Provision**
3. Original VM untouched — test new thin VM before cutover
4. **Pros:** Zero risk, verified backup as byproduct, works with any Veeam edition
5. **Cons:** Needs extra space temporarily, requires separate backup repository

### Strategy 2: vmkfstools Clone (No Extra Software)
```bash
# From ESXi shell
vmkfstools -i /vmfs/volumes/<ds>/<vm>/<disk>.vmdk \
          -d thin \
          /vmfs/volumes/<ds>/<vm>/<disk>-thin.vmdk
```
Then detach old disk from VM, attach new thin one.
- **Pros:** Block-level fast, no backup software needed
- **Cons:** Manual VMDK swap, needs free space equal to disk size, risky if command typoed

### Strategy 3: Storage vMotion (vCenter Required)
- Migrate VM → **Change datastore only** → Disk format: **Thin Provision**
- **Requires two datastores** — can't Storage vMotion to the same datastore
- **Requires vCenter** — won't work on standalone ESXi host

### Strategy 4: VMware vCenter Converter (Standalone Free Tool)
- Point to running/powered-off VM → Convert to new thin VM
- **Pros:** Free, works remotely from any Windows machine
- **Cons:** Can be flaky, needs Converter agent on source VM

### ⛔ What Does NOT Work
- **SDelete -z + vmkfstools --punchzero** — Only works on THIN disks. For thick disks, the space is already allocated on the datastore and punching zeroes doesn't reclaim it.
- **Shrinking the disk** in vSphere — Only possible for thin disks or when VMDK contents actually shrink.

## Veeam-Specific Tips

1. **Validate backup repository is on a DIFFERENT datastore** than the source VM. If they share the same datastore, there's no room for restore.
2. **Veeam Quick Migration** (Enterprise+) — Backup → Instant Recovery → Migrate to thin — avoids full restore step.
3. **Changed Block Tracking (CBT)** — `.ctk.vmdk` files are Veeam's CBT tracking. Safe to leave alone.
4. **Veeam-Backup VM logs** — Check `/vmfs/volumes/<ds>/Veeam-Backup(4.25)/` for old `vmware-*.log` files that can be cleaned.

## Verification After Conversion

- [ ] New VM powers on with all disk volumes intact
- [ ] Applications/services start correctly
- [ ] Network connectivity works (same IP/MAC)
- [ ] Event logs are clean
- [ ] Disk shows as thin provisioned in vSphere (`ls -lh` on flat vmdk < provisioned size)
- [ ] Old VM kept offline for 1-2 weeks as fallback
- [ ] Veeam backup job updated to back up the new VM
