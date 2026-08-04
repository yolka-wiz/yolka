# step-ca — Internal Enterprise Certificate Authority

## Overview

step-ca (Smallstep) is a modern internal CA that supports ACME protocol, REST API, and automatic certificate renewal. It runs as a single binary and can be deployed in a container or natively.

## Installation

```bash
# Check latest release at https://github.com/smallstep/cli/releases
curl -fsLO https://github.com/smallstep/cli/releases/download/v0.28.5/step_linux_0.28.5_amd64.tar.gz
tar xzf step_linux_0.28.5_amd64.tar.gz
sudo cp step_0.28.5/bin/step /usr/local/bin/
step version  # verify
```

## CA Initialization

Run `step ca init` once. It generates:
- Root CA key (ECDSA P-256) + certificate (10yr default)
- Intermediate CA key + certificate (signed by root)
- Database directory (BadgerDB)
- Config files for the step-ca server

```bash
step ca init \
  --name="Internal Enterprise CA" \
  --dns="ca.internal.local" \
  --dns="localhost" \
  --dns="step-ca-step-certificates.ca.svc.cluster.local" \
  --address=":9000" \
  --provisioner="admin" \
  --password-file=<(echo -n "YourCApassword2026!")
```

Files created in `~/.step/`:

| Path | Purpose |
|------|---------|
| `certs/root_ca.crt` | Root CA cert — distribute to every device |
| `certs/intermediate_ca.crt` | Intermediate CA cert |
| `secrets/root_ca_key` | Root CA key — **keep offline / encrypted backup** |
| `secrets/intermediate_ca_key` | Intermediate CA key (password-protected) |
| `secrets/password` | The password you supplied |
| `config/ca.json` | step-ca server config |
| `config/defaults.json` | Default values for `step ca certificate` commands |
| `db/` | BadgerDB (certificate database) |

Root CA fingerprint (needed for `step ca bootstrap` from clients):
```bash
step certificate fingerprint ~/.step/certs/root_ca.crt
```

## Deploying step-ca in k3s (Helm)

```bash
# Add repo
helm repo add smallstep https://smallstep.github.io/helm-charts
helm repo update

# Create namespace
kubectl create namespace ca

# Pre-initialize (on first deploy only)
# Copy the ~/.step/ data into k8s secrets manually, or use an init container.
# For simple setups, skip the Helm chart entirely and use the CLI directly.

# Install
helm upgrade --install step-ca smallstep/step-certificates \
  --namespace ca \
  --set persistence.enabled=true \
  --set persistence.size=5Gi \
  --set inject.enabled=true \
  --wait
```

**Known issue:** The Helm chart expects CA data to already exist. If you install it fresh without pre-initialization, the pod fails with `error reading "/home/step/certs/intermediate_ca.crt": no such file or directory`. Either:
1. Pre-populate the PVC with `step ca init` output
2. Add an init container that runs `step ca init`
3. Use the CLI-based workflow instead (below)

## CLI-based Certificate Creation (No Helm Server Needed)

For environments where the CA doesn't need to be a 24/7 API server (small homelabs), generate certs directly from the initialized CA:

### 1. Create a CSR

```bash
# Code signing key (RSA 4096)
openssl genrsa -out codesign.key 4096
openssl req -new -key codesign.key -subj "/CN=Internal Code Signing/O=Internal Enterprise CA" -out codesign.csr

# Web server key (RSA 2048)
openssl genrsa -out wildcard.key 2048
openssl req -new -key wildcard.key -subj "/CN=*.internal.local/O=Internal Enterprise CA" -out wildcard.csr
```

### 2. Sign with the CA

```bash
# Write password to file (avoids CLI parsing issues with process substitution)
echo -n "YourCApassword2026!" > /tmp/ca-pass.txt

# Code signing (10 years, codeSigning EKU)
cat > /tmp/codesign-template.json <<'EOF'
{"keyUsage":["digitalSignature"],"extKeyUsage":["codeSigning"]}
EOF

step certificate sign codesign.csr \
  ~/.step/certs/intermediate_ca.crt \
  ~/.step/secrets/intermediate_ca_key \
  --password-file=/tmp/ca-pass.txt \
  --not-after=87660h \
  --template=/tmp/codesign-template.json \
  --bundle \
  codesign.crt

# Wildcard web server (SANs for all internal domains)
cat > /tmp/server-template.json <<'EOF'
{"keyUsage":["digitalSignature","keyEncipherment"],"extKeyUsage":["serverAuth"],"sans":["DNS:*.internal.local","DNS:core-srv","DNS:localhost","IP:192.168.4.109"]}
EOF

step certificate sign wildcard.csr \
  ~/.step/certs/intermediate_ca.crt \
  ~/.step/secrets/intermediate_ca_key \
  --password-file=/tmp/ca-pass.txt \
  --not-after=87660h \
  --template=/tmp/server-template.json \
  --bundle \
  wildcard.crt
```

### 3. Distribute

| File | Distribute To |
|------|---------------|
| `root_ca.crt` | Every device in the fleet (via GPO, antivirus panel, or manual import) |
| `codesign.crt` + `codesign.key` | Build/CI machines for signing scripts |
| `wildcard.crt` + `wildcard.key` | Web servers, FortiGate admin UI, ESXi host UI, VoIP web UI |

On Windows, convert to PFX for easier import:
```bash
openssl pkcs12 -export -in wildcard.crt -inkey wildcard.key -certfile full-chain.crt -passout pass: -out wildcard.pfx
```

## Password Syntax Pitfall

**Always use `--password-file=/path` (equals sign)** not `--password-file /path` (space). With a space, process substitution adds an unexpected positional argument, and the command fails with:

```
too many positional arguments were provided in 'step certificate sign <csr-file> <crt-file> <key-file>'
```

**WRONG:** `--password-file <(echo -n "pass")` → expands to 2+ args
**RIGHT:** `--password-file=/tmp/pass.txt` → single arg

## CA Server (step-ca in k3s)

If you want ACME auto-renewal (certificate lifecycle management via cert-manager or step-issuer), deploy step-ca as a proper k8s service:

```bash
# After initial deployment, initialize the CA:
kubectl exec -n ca step-ca-step-certificates-0 -- step ca init \
  --name="..." --dns="..." --address=":9000" \
  --provisioner="admin" \
  --password-file=/home/step/secrets/password

# The ACME endpoint is at: https://step-ca.ca.svc.cluster.local/acme/acme
```

Then configure cert-manager with a `ClusterIssuer` that uses the step-ca ACME endpoint.
