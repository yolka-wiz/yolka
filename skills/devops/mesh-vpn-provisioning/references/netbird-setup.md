# NetBird Setup Reference

Real-world session details from installing NetBird v0.75.0 on Debian 13 (Trixie).

## Installation

```bash
curl -fsSL https://pkgs.netbird.io/install.sh | sh
```

The script adds the NetBird apt repository and installs the `netbird` package. The systemd service is started and enabled automatically.

## Connecting with a Setup Key (Headless Server)

```bash
sudo netbird up --setup-key <UUID-KEY> --allow-server-ssh
```

### Observed Output on Success
```
Connected
```

### Status Fields After Connection

| Field | Example Value |
|-------|---------------|
| NetBird IP | `100.70.153.245/16` |
| FQDN | `agent.netbird.cloud` |
| Interface | `wt0` (WireGuard Kernel) |
| Management | `Connected to https://api.netbird.io:443` |
| Signal | `Connected to https://signal.netbird.io:443` |
| Relay | `turns:turn.netbird.io:443?transport=tcp` (Available) |
| STUN | `stun:stun.netbird.io:443` and `:5555` (may show Unavailable — expected) |
| SSH Server | `Disabled` (system OpenSSH on port 22 still works) |
| Peers | `0/0 Connected` until another device joins the network |
| WireGuard port | `51820` |

## Setup Key Format

Standard UUID format:
```
DD2977A8-8B56-40F9-A3F5-683D0A801790
```

## Service Persistence

The `netbird.service` systemd unit is installed and enabled automatically:
```bash
systemctl is-enabled netbird  # → "enabled"
systemctl status netbird      # → active (running)
```

## SSH Access via NetBird

Once connected, SSH to the NetBird IP works just like a local IP:
```bash
ssh agent@100.70.153.245
```

No firewall configuration is needed on the server — the NetBird IP is a local interface, and system OpenSSH listens on 0.0.0.0:22.

## Management Dashboard

NetBird's cloud dashboard is at: https://app.netbird.io
Default flags send traffic to: `--admin-url https://app.netbird.io:443`

## Known Quirks

- **--allow-server-ssh flag is unreliable**: In some environments the NetBird SSH server remains disabled despite the flag. The system OpenSSH on port 22 is sufficient for SSH access.
- **STUN servers may show as Unavailable**: `stun:stun.netbird.io:443` and `stun:stun.netbird.io:5555` may report "context canceled" — this doesn't affect connectivity if TURN relays are available.
- **Lazy connection**: Peers are not immediately connected. The first SSH attempt may have slight latency (1-2s) while the P2P/relay path is established.
- **Interface type**: Kernel WireGuard (wt0) is preferred over userspace — better performance. If the kernel module is unavailable, NetBird falls back to userspace.
