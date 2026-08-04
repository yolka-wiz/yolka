---
name: mesh-vpn-provisioning
description: Install mesh VPNs on headless Linux for remote SSH access.
category: devops
version: 1.0.0
---

# Mesh VPN Provisioning

Provision a headless Linux server on a mesh VPN (WireGuard-based overlay network) to enable persistent remote SSH access from anywhere — bypassing NAT, CGNAT, or firewalls without port forwarding.

## When to Use

- User says "install NetBird/Tailscale/ZeroTier so I can SSH remotely"
- A server needs remote management access but has no public IP or static port forwarding
- Setting up a temporary management backchannel into an isolated LAN segment

Don't use for: site-to-site VPNs (IPsec/WireGuard tunnels between networks), client-to-site VPNs (OpenVPN/WireGuard road warrior), or when SSH port forwarding over existing infrastructure already works.

## General Workflow

### Phase 0: Preflight Checks

1. **Verify internet connectivity** to the VPN provider and its infrastructure:
   ```bash
   curl -sI --max-time 5 https://<provider>.io
   curl -sI --max-time 5 https://api.<provider>.io
   ```

2. **Verify SSH is running and reachable** on the server (it will be reachable via the mesh IP after connection):
   ```bash
   systemctl status ssh --no-pager
   ss -tlnp | grep ':22'
   ```

3. **Check for port conflicts**: Mesh VPNs often listen on UDP port 51820 (WireGuard). Verify it's free:
   ```bash
   ss -ulpn | grep 51820
   ```

### Phase 1: Install the Mesh Client

**NetBird — Debian/Ubuntu (official repo):**
```bash
curl -fsSL https://pkgs.netbird.io/install.sh | sh
```

**Tailscale — Debian/Ubuntu (official repo):**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

**ZeroTier — Debian/Ubuntu:**
```bash
curl -s https://install.zerotier.com | sh
```

> **Security note:** All three use `curl | sh` — review the script first, or use the package-based install method listed in each provider's docs. For NetBird: `sudo apt install netbird` after adding their GPG key and repo.

### Phase 2: Authenticate & Connect

For **headless servers without a browser**, the only reliable auth method is a **setup key** (pre-authentication token) generated from the provider's admin dashboard.

**NetBird:**
```bash
sudo netbird up --setup-key <UUID-KEY> --allow-server-ssh
```
Output: `Connected`

**Tailscale:**
```bash
sudo tailscale up --authkey <KEY>
```

**ZeroTier:**
```bash
sudo zerotier-cli join <NETWORK-ID>
```

#### SSO Auth on Headless (fallback when no setup key)

When only SSO is available and there's no browser on the server:
- Use `--no-browser --qr` to display a QR code
- Scan the QR from your phone or desktop browser
- The QR encodes a login URL that redirects back to the VPN provider for OAuth/SSO

### Phase 3: Verify Connection

```bash
# NetBird
netbird status --detail      # Shows IP, FQDN, peers, relay status
ip addr show wt0             # NetBird WireGuard interface

# Tailscale
tailscale status             # Shows IP, connected peers
ip addr show tailscale0      # Tailscale interface

# General
ping -c2 <mesh-ip>           # Loopback test on the mesh interface
```

**Key items to check in status output:**
| Field | Expected | Meaning |
|-------|----------|---------|
| Management / Control | Connected | Can reach the coordinator server |
| Signal / DERP | Connected | Can reach the relay infrastructure |
| Interface type | Kernel | WireGuard kernel module (preferred over userspace) |
| Peers | > 0 | Other devices visible on the mesh |
| SSH Server (NetBird) | Enabled | Only if `--allow-server-ssh` was set |

### Phase 4: Enable SSH Access

System OpenSSH (port 22) is reachable through the mesh interface automatically — no firewall changes needed on the server because the mesh IP is a local interface.

**Connect from a peer:**
```bash
ssh user@<mesh-ip>
# or if DNS is set up:
ssh user@<hostname>.<provider>.cloud
```

**NetBird's built-in SSH server** (separate from system SSH — uses JWT token auth):
```bash
# Enable on initial connect:
sudo netbird up --setup-key <KEY> --allow-server-ssh

# Enable on an already-connected peer:
# Re-run netbird up with the flag — it's idempotent
sudo netbird up --setup-key <KEY> --allow-server-ssh
```

### Phase 5: Service Persistence (Auto-reconnect)

All three providers install a systemd service that auto-starts on boot:

```bash
# NetBird
systemctl is-enabled netbird      # Should be "enabled"

# Tailscale
systemctl is-enabled tailscaled   # Should be "enabled"

# ZeroTier
systemctl is-enabled zerotier-one # Should be "enabled"
```

If disabled, enable it:
```bash
sudo systemctl enable <service>
```

### Phase 6: Firewall Considerations

The server needs **outbound** access to the mesh provider's infrastructure:
- **NetBird**: `api.netbird.io:443`, `signal.netbird.io:443`, `turn.netbird.io:443` (TURN relay via TCP/443), plus STUN
- **Tailscale**: DERP relay servers (TCP/443, UDP/3478), coordination server
- **ZeroTier**: planet/moon servers (TCP/UDP 9993)

All three use WireGuard at the data plane (UDP). The WireGuard port is:
- **NetBird**: UDP 51820 (configurable with `--wireguard-port`)
- **Tailscale**: Random UDP port (configurable)
- **ZeroTier**: UDP 9993

Ensure the server's egress firewall allows these. If behind a corporate proxy, the initial connection to the coordination/API server must go through the proxy (most mesh VPNs support HTTPS CONNECT proxy).

## Pitfalls

- **SSO-only network**: If the user's network was created with SSO-only onboarding and no setup keys have been generated, you can't join a headless server. The user must either (a) generate a setup key from the admin dashboard, or (b) you can use the `--qr` flag to show a QR code and have them authenticate from their phone.
- **DNS conflicts**: NetBird and Tailscale both manage system DNS (`/etc/resolv.conf`). If you have a local DNS resolver (dnsmasq, systemd-resolved), use `--disable-dns` to avoid resetting the resolver config.
- **SSH Server: Disabled even with flag**: NetBird's `--allow-server-ssh` flag enables a separate SSH server (not system OpenSSH). System SSH on port 22 still works through the mesh interface regardless of this flag. If the flag doesn't seem to stick, the system SSH is sufficient.
- **Multiple interfaces**: The mesh VPN creates a new network interface. The server remains reachable on both its local LAN IP and its mesh IP simultaneously.
- **Lazy connection mode**: NetBird uses "lazy connection" — peers are not immediately connected. They establish direct P2P or relay paths only when traffic is sent. Initial ping/SSH to a new peer may have 1-2s latency while the connection is being negotiated.
- **Relay dependency**: If direct P2P NAT traversal fails (symmetric NAT, double NAT), traffic routes through a relay server (TURN for NetBird, DERP for Tailscale). This adds latency and bandwidth is billed to the provider. For low-latency needs, ensure P2P works.
- **IPv6 overlay**: Most mesh VPNs assign an IPv6 overlay address by default. If the server's LAN doesn't support IPv6, the mesh IPv6 address won't be reachable from the LAN — use IPv4 for cross-network connectivity.

## Verification Checklist

- [ ] Internet connectivity verified (curl to provider domain)
- [ ] SSH is running and listening on all interfaces
- [ ] Mesh client installed and service enabled in systemd
- [ ] Setup key used for headless auth (or QR code scanned)
- [ ] `netbird status` or `tailscale status` shows Connected
- [ ] Mesh interface (wt0 / tailscale0) has an IP
- [ ] Can SSH to the mesh IP from a peer on the same network
- [ ] Service persists across reboot (systemctl is-enabled)
- [ ] Firewall allows outbound UDP to WireGuard port + TCP 443 to relays

## Related Files

- `references/netbird-setup.md` — NetBird-specific setup details, IP ranges, FQDN patterns, relay URLs from a real installation
