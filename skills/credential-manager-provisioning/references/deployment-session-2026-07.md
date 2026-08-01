# OpenBao Deployment Session — July 2026

## Target Server

- **Hostname:** core-srv
- **IP:** 192.168.4.120 (also br13: 192.168.13.109)
- **OS:** Debian 13 (Trixie), kernel 6.12.95
- **User:** core / Core8orn@
- **Role:** K3s single-node cluster + Incus VM host

## Deployment Summary

OpenBao v2.6.1 deployed as Docker container using `docker.io` from Debian repo (docker.com was firewalled). Configured with file storage backend at `/opt/bao/data`.

### Access

| Endpoint | URL |
|----------|-----|
| **API** | `http://192.168.4.120:8200` |
| **Web UI** | `http://192.168.4.120:8200/ui` |
| **Root Token** | `s.l5pNqhyBU3WJQXn2Pkue432f` |

### Secrets Engines Enabled

| Engine | Path |
|--------|------|
| KV v2 | `secret/` |
| PKI | `pki/` |
| SSH | `ssh/` |
| Transit | `transit/` |

### Unseal Keys (threshold 2 of 3)

```
Key 1:  7v7zCnAxoBbyljEHI77PS7Z/3vZNJj0DWtFDFT7V3KML
Key 2:  t6pH9FHCsNXcJB1dhvVh+qB5eLSMAB43+utFkuPqpXli
Key 3:  YsQ2Bh2LhsZrlero4VZ9K1a5fyzfrBLtPeqF2R1LHGft
```

### Credential Files on Server

| Path | Contents |
|------|----------|
| `/opt/bao/creds/openbao-credentials.txt` | Master credentials (token + keys) |
| `/opt/bao/unseal.sh` | Auto-unseal script (uses key 1 + 2) |

### User Convenience

Added to `core@`'s `~/.bashrc`:
```bash
export BAO_ADDR=http://127.0.0.1:8200
export BAO_TOKEN=s.l5pNqhyBU3WJQXn2Pkue432f
alias bao="sudo docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=s.l5pNqhyBU3WJQXn2Pkue432f openbao bao"
```

### Remote Access (from Hermes agent at 192.168.13.18)

```bash
# SSH to core-srv
ssh core@192.168.4.120

# Or via key (agent's SSH key was added to authorized_keys)
ssh -i ~/.ssh/id_ed25519 core@192.168.4.120

# API call from Hermes server
curl -H "X-Vault-Token: s.l5pNqhyBU3WJQXn2Pkue432f" \
  http://192.168.4.120:8200/v1/secret/data/test
```
