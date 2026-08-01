---
name: credential-manager-provisioning
description: OSS secret manager for passwords, SSH, GPG, and TLS certs.
category: devops
---

# Credential Manager Provisioning

Deploy a self-hosted OSS credential and secret manager on a Debian server using Docker. Covers OpenBao (MPL 2.0 — fully OSS fork of HashiCorp Vault), including initialization, unsealing, secrets engine configuration, credential backup, and remote API access.

## When to Use

- User needs a self-hosted credential manager for **passwords + SSH keys + GPG keys + TLS certificates** in one place
- User wants OSS (not BSL-licensed like HashiCorp Vault since 2023)
- The workload spans multiple secret types that Vaultwarden or Passbolt can't handle natively (PKI, SSH engine)
- User specified requirements: OSS, remote-accessible via API, web UI optional

## Why Not Alternatives

| Tool | Can't handle |
|------|-------------|
| **Vaultwarden** | SSH keys (notes only), GPG keys (attachments only), certificates (no CA) |
| **Passbolt** | SSH keys, certificates |
| **pass/gopass** | Web UI, remote API, certificates |
| **HashiCorp Vault** | **License** — BSL 1.1 since 2023, not fully OSS |

## Architecture Decision

**OpenBao** (v2.6.1+) — API-compatible with Vault, Linux Foundation-backed, MPL 2.0.

### Layers

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Host** | Debian 12/13 | Server on LAN |
| **Container runtime** | Docker | `docker.io` from Debian repo when CE is blocked |
| **Secret engine** | OpenBao (Docker image) | `openbao/openbao:latest` |
| **Storage** | File backend | `/opt/bao/data/` — single dir, easy to back up |
| **Access** | REST API (`:8200`) + Web UI (`:8200/ui`) | No TLS for LAN, add cert for WAN |

### Secrets Engines to Enable

| Engine | Path | Purpose |
|--------|------|---------|
| KV v2 | `secret/` | Passwords, API keys, text secrets, GPG private keys |
| PKI | `pki/` | TLS certs (internal CA), cert issuance/revocation |
| SSH | `ssh/` | SSH key signing, OTP, dynamic credential injection |
| Transit | `transit/` | Encrypt/decrypt ops (GPG-style signing/verification) |

## Deployment Workflow

### Phase 1: Docker Setup

Check if Docker exists. If not, install from Debian repo (works when docker.com is firewalled):

```bash
# Check
which docker || echo "No Docker"

# Install from Debian repo
sudo apt-get install -y docker.io
```

### Phase 2: Prepare Directories and Config

```bash
sudo mkdir -p /opt/bao/{config,data}
sudo chown -R 100:1000 /opt/bao/
```

Write `/opt/bao/config/config.hcl`:

```hcl
storage "file" {
  path = "/opt/bao/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

api_addr = "http://<SERVER_IP>:8200"
cluster_addr = "https://<SERVER_IP>:8201"
ui = true
disable_mlock = true
```

> **Pitfall:** `disable_mlock = true` is required in Docker. Without it the container exits immediately. For production, use `--cap-add=IPC_LOCK` and remove this line.

### Phase 3: Start Container

```bash
sudo docker pull docker.io/openbao/openbao:latest
sudo docker run -d \
  --name openbao \
  --restart unless-stopped \
  -p 8200:8200 \
  -v /opt/bao/config:/opt/bao/config:ro \
  -v /opt/bao/data:/opt/bao/data \
  -e BAO_SKIP_CHOWN=true \
  openbao/openbao server -config=/opt/bao/config/config.hcl
```

Verify: `sudo docker ps --filter name=openbao`

### Phase 4: Initialize

The CLI uses the `bao` binary inside the container:

```bash
sudo docker exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator init \
  -key-shares=3 -key-threshold=2 -format=json
```

**Pitfall:** If `BAO_ADDR` is not set to `http://`, the CLI defaults to HTTPS and fails with: `http: server gave HTTP response to HTTPS client`. Always set `BAO_ADDR=http://127.0.0.1:8200` when TLS is disabled.

Save the output — it contains:
- `unseal_keys_b64` (3 keys, 2 needed to unseal)
- `root_token` (admin access)

### Phase 5: Unseal

```bash
sudo docker exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator unseal <KEY1>
sudo docker exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator unseal <KEY2>
```

Verify: `sudo docker exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao status` → `Sealed: false`

### Phase 6: Enable Engines

```bash
ADDR=http://127.0.0.1:8200
TOKEN=s.<root-token>

sudo docker exec -e BAO_ADDR=$ADDR -e BAO_TOKEN=$TOKEN openbao bao secrets enable -path=secret kv-v2
sudo docker exec -e BAO_ADDR=$ADDR -e BAO_TOKEN=$TOKEN openbao bao secrets enable -path=pki pki
sudo docker exec -e BAO_ADDR=$ADDR -e BAO_TOKEN=$TOKEN openbao bao secrets enable -path=ssh ssh
sudo docker exec -e BAO_ADDR=$ADDR -e BAO_TOKEN=$TOKEN openbao bao secrets enable -path=transit transit

# Verify
sudo docker exec -e BAO_ADDR=$ADDR -e BAO_TOKEN=$TOKEN openbao bao secrets list
```

### Phase 7: Save Credentials

Write to `/opt/bao/creds/openbao-credentials.txt`:

```
Server:   http://<SERVER_IP>:8200
Root Token:  s.<token>
Unseal Key 1:  <key1>
Unseal Key 2:  <key2>
Unseal Key 3:  <key3>
Web UI:  http://<SERVER_IP>:8200/ui
Login:   Root Token
```

### Phase 8: Auto-Unseal Script

Create `/opt/bao/unseal.sh`:

```bash
#!/bin/bash
BAO_ADDR=http://127.0.0.1:8200
KEY1="<key1>"
KEY2="<key2>"
docker exec -e BAO_ADDR=$BAO_ADDR openbao bao operator unseal $KEY1 > /dev/null 2>&1
docker exec -e BAO_ADDR=$BAO_ADDR openbao bao operator unseal $KEY2 > /dev/null 2>&1
echo "OpenBao unsealed"
```

```bash
sudo chmod +x /opt/bao/unseal.sh
```

## Verification

### From the server

```bash
# Health
curl -s http://127.0.0.1:8200/v1/sys/health

# Write + read
curl -s -H "X-Vault-Token: s.<token>" \
  -X POST -d '{"data":{"test":"hello"}}' \
  http://127.0.0.1:8200/v1/secret/data/test

curl -s -H "X-Vault-Token: s.<token>" \
  http://127.0.0.1:8200/v1/secret/data/test
```

### From a remote machine on the LAN

```bash
curl -s http://<SERVER_IP>:8200/v1/sys/health
# Expected: {"sealed":false,"initialized":true,"version":"2.6.1"}
```

## User Convenience (shell alias)

Add to `~/.bashrc` on the server:

```bash
export BAO_ADDR=http://127.0.0.1:8200
export BAO_TOKEN=s.<root-token>
alias bao="sudo docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=s.<root-token> openbao bao"
```

Then `source ~/.bashrc` and use `bao secrets list`, `bao kv put`, etc.

## Pitfalls

- **`BAO_ADDR` must use `http://` not `https://`** when TLS is disabled. The `bao` CLI defaults to HTTPS.
- **`disable_mlock = true` required in Docker** — without it the process can't lock memory pages and exits.
- **Container UID/GID**: OpenBao runs as UID 100 / GID 1000 inside the container. The host dirs need matching ownership or `BAO_SKIP_CHOWN=true` to avoid permission errors.
- **Bao command name**: The binary is `bao`, not `vault` or `openbao`. This trips up users coming from HashiCorp Vault.
- **Unseal on every restart**: The container auto-starts via systemd (`--restart unless-stopped`) but stays sealed. You need 2 of 3 keys to unseal after each reboot.
- **No TLS by default**: The guide uses plain HTTP for simplicity. For production, configure TLS in the listener block or put a reverse proxy (Traefik/Nginx) in front.
- **sudo hostname resolution**: On some Debian systems, `sudo` can't resolve the hostname, causing warnings but not failures. Fix with `echo '127.0.1.1 <hostname>' | sudo tee -a /etc/hosts`.

## Post-Deployment Tasks

1. **Create non-root user**: `bao auth enable userpass` — avoid using root token for daily ops
2. **Configure PKI**: `bao write pki/root/generate/internal common_name="Internal CA" ttl=87600h`
3. **Backup /opt/bao/data/** regularly — this is the entire vault state
4. **Add TLS** for production (listener cert or reverse proxy)

## Related

- [OpenBao Docs](https://openbao.org/docs/)
- [Vault API Docs](https://developer.hashicorp.com/vault/api-docs) — compatible with OpenBao
