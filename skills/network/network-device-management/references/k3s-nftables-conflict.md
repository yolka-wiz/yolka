# Case Study: k3s Pod-to-Service Networking Broken by nftables

## Symptom

After installing k3s on Debian 13 with a custom nftables firewall, all system pods crash-looped with:

```
local-path-provisioner: Error starting daemon: Get "https://10.43.0.1:443/api/v1/...": dial tcp 10.43.0.1:443: connect: connection refused
```

## Debugging Trace

### Step 1 — Identify the failure mode

- `kubectl get nodes` → node Ready (k3s API works from host)
- `kubectl get pods -A` → all system pods CrashLoopBackOff or Error
- `kubectl logs <pod>` → all show `connection refused` on the kubernetes service IP (10.43.0.1:443)

### Step 2 — Differentiate host vs pod

```bash
# FROM THE HOST — this works
curl -sk https://10.43.0.1:443/version  # returns API version JSON

# FROM INSIDE A POD — this fails
kubectl run test --image=busybox -- wget http://10.43.0.1:443/version
# → "Connection refused"
```

This narrows the problem to **service routing from pod network** specifically — not the API server itself.

### Step 3 — Check the NAT rules

```bash
sudo nft list ruleset | grep -i "DNAT"
```

Output shows: `# Warning: XT target DNAT not found`

This is the smoking gun. The k3s service proxy uses iptables-nft (iptables rules translated to nftables via the nft_compat kernel module). Our native nftables ruleset was interfering with these compatibility rules.

**Additional clues in `nft list ruleset` output:**
- `# Warning: XT target DNAT not found` — the DNAT target handler is missing
- `# Warning: XT target MARK not found` — the MARK target handler is missing
- These warnings appear for ALL iptables-nft rules in the `table ip nat` and `table ip filter` tables

### Step 4 — Root cause identification

Our `nftables.conf` started with:

```
flush ruleset
```

This single command destroys **all** nftables rules across all tables, including the `table ip nat` rules that k3s's iptables-nft shim creates for DNAT (service IP → node IP translation). After `flush ruleset`, the KUBE-SERVICES chain and all DNAT rules are gone, so traffic from pods to `10.43.0.1:443` never gets NAT'd to `127.0.0.1:6443`.

The iptables-nft compatibility shim (`nft_compat` kernel module) translates iptables rules into nftables internally. The `flush ruleset` command is **nftables-native** and doesn't know about or preserve the iptables-nft rules. So the flush is effectively a nuke from orbit for all container networking.

### Step 5 — Fix

```bash
# Disable the conflicting native nftables service
sudo systemctl stop nftables
sudo systemctl disable nftables
sudo rm -f /etc/nftables.conf

# Restart k3s to regenerate iptables-nft rules
sudo systemctl restart k3s
```

After this, all system pods started correctly:
- coredns → Running
- local-path-provisioner → Running
- metrics-server → Running
- traefik → Running

## Key Insight

On systems running iptables-nft compatibility (k3s, Docker, most container runtimes), **never use `flush ruleset`** in a native nftables configuration file. It clears the compatibility shim rules that the container runtime depends on.

## Alternative Approaches If You Must Use nftables

1. **Use `add table`/`add chain`/`add rule`** instead of `flush ruleset` + `table ... { ... }` definition blocks. This adds your rules alongside existing rules rather than replacing everything.

2. **Use iptables-nft syntax** for your firewall rules instead of native nftables syntax (`iptables ...` commands). This keeps everything in the same compatibility layer as the container runtime.

3. **Apply firewall rules AFTER k3s starts** and use `nft -f` without `flush ruleset` to add rules incrementally. The k3s-created rules are present after startup, so incremental adds won't interfere.

4. **Use `ufw`** (Uncomplicated Firewall) which manages iptables-nft rules correctly alongside Docker/k3s — it was designed for coexistence.

## Verification Checklist

- [ ] `kubectl get nodes` — node is Ready
- [ ] `kubectl get pods -A` — all system pods Running (not CrashLoopBackOff)
- [ ] `kubectl run test --image=busybox --rm -q -- wget -q -O- http://10.43.0.1:443/version` — returns API version
- [ ] `sudo nft list ruleset | grep -i "DNAT"` — no `XT target DNAT not found` warnings
- [ ] `sudo nft list table ip nat | grep -c "KUBE-SERVICES"` — returns > 0
