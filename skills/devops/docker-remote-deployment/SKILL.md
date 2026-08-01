---
name: docker-remote-deployment
description: Deploy Docker containers on remote Linux servers over SSH.
category: devops
version: 1.0.0
---

# Docker Remote Deployment

Build Docker images and run containers on remote Linux servers via SSH. Covers the build-time traps (missing `go.sum`, heredoc-stripped quotes) and the deployment patterns (port mapping, volume mounts, restart policy, lifecycle).

## When to Use

- Building a Docker image on a remote server (no local Docker)
- Deploying a containerized application to a remote Linux host
- Running a daemon-style container (always-on, restart policy, persistent data)
- Any deployment where the Dockerfile needs on-server fixes (missing deps, broken go.sum, etc.)

## Workflow Overview

```
Clone repo on remote → Fix Dockerfile if needed → Build image → Run container → Verify
```

All steps happen over SSH. The Docker CLI runs with `sudo` unless the remote user is in the `docker` group.

## Go Docker Build Fix: Missing `go.sum`

Many Go projects exclude `go.sum` via `.gitignore`. The standard Dockerfile pattern `go mod download 2>/dev/null || true` silently fails — it downloads modules but doesn't generate `go.sum`. The build fails at `go build` with:

```
missing go.sum entry for module providing package github.com/xxx/yyy
```

**Fix — replace with `go mod tidy` twice:**

```dockerfile
COPY go.mod ./
RUN go mod tidy

COPY . .
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /out/app ./cmd/app
```

- First `go mod tidy` (after `COPY go.mod ./`) downloads deps + generates `go.sum`
- Second `go mod tidy` (after `COPY . .`) reconciles with all source present
- Then `go build` has the complete module graph

**Always rebuild with `--no-cache`** when fixing a Dockerfile — cached broken layers persist:

```bash
ssh user@host "sudo docker build --no-cache -t myapp:latest /path/to/repo"
```

## Dockerfile JSON Syntax in SSH Heredocs

JSON array syntax in Dockerfiles (`ENTRYPOINT ["binary"]`, `CMD ["-flag", "val"]`, `-ldflags="-s -w"`) **loses its quotes** when written via bash heredoc over SSH:

```bash
# ❌ FAILS — quotes stripped:
ssh user@host 'cat > Dockerfile << EOF
ENTRYPOINT ["/usr/local/bin/app"]
EOF'
# Results in:  ENTRYPOINT [/usr/local/bin/app]  ← invalid!
```

**Fix — use Python heredocs** for Dockerfiles with JSON syntax:

```bash
ssh user@host python3 << 'PYEOF'
dockerfile = r'''FROM golang:1.26-alpine AS builder
ENTRYPOINT ["/usr/local/bin/app"]
CMD ["-config", "/work/config.toml"]
'''
with open('/tmp/repo/Dockerfile', 'w') as f:
    f.write(dockerfile)
print("Dockerfile written OK")
PYEOF
```

The `r'''...'''` raw triple-quoted string preserves all content literally.

**Simpler alternative:** write the file locally with `write_file`, then `scp`:

```python
from hermes_tools import write_file, terminal
write_file(path="Dockerfile", content=dockerfile_content)
terminal(f"scp Dockerfile user@host:/tmp/repo/Dockerfile")
```

## Running a Daemon Container

Basic pattern for a long-running daemon with persistent data and exposed ports:

```bash
docker run -d \
  --name <container-name> \
  --restart unless-stopped \
  -v /host/data/path:/container/work/path \
  -p HOST_PORT:CONTAINER_PORT \
  -p ANOTHER_PORT:ANOTHER_PORT \
  <image-name>:<tag>
```

| Flag | Purpose |
|------|---------|
| `-d` | Detached — run in background |
| `--restart unless-stopped` | Auto-restart on crash/reboot, but not if manually stopped |
| `-v host:container` | Mount host directory for persistent data (config, state, output) |
| `-p host:container` | Expose container port on host interface |

**Stop + recreate when updating:**

```bash
sudo docker rm -f <container-name> 2>/dev/null
sudo docker run -d --name <container-name> --restart unless-stopped ...
```

## Verification After Deployment

Check three things:

```bash
# 1. Container is running
sudo docker ps --filter name=<name> --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# 2. Application logs show correct startup
sudo docker logs <name> --tail 20

# 3. Service is reachable from the network
curl -s http://<host-ip>:<port>/api/health
```

For subscription-type services, also verify the content endpoint:

```bash
curl -s -w "\nHTTP %{http_code}" http://<host-ip>:<port>/<sub-path>
```

## Pitfalls

- **`go mod download` with error suppression** — The `2>/dev/null || true` pattern hides the `go.sum` failure. Always inspect build output when it fails, even if it says "OK".
- **Dockerfile heredoc stripping** — Bash heredocs remove quotes from Dockerfile JSON arrays. Use Python heredocs or local write+scp.
- **Cached broken layers** — Without `--no-cache`, Docker reuses the cached `RUN go mod download` layer even after you fix the Dockerfile. Always `--no-cache` after a Dockerfile fix.
- **User not in docker group** — The remote user may need `sudo` for Docker commands. Check with `ssh user@host "docker ps"` first; if permission denied, prefix commands with `sudo`.
- **Port already in use** — Check `ss -tlnp` on the host before binding. If another container or service uses the port, either stop it or change the host-side port mapping (`-p ALTERNATE:CONTAINER`).
- **Volume path permissions (most common silent failure)** — If the container's logs show successful work ("cycle complete", "data written") but output files never appear on the host disk, the container user cannot write to the bind-mounted volume.\n  \n  **Diagnose:** `docker exec <name> id` — Alpine's `nobody` is uid **65534**, Debian's is uid **65534** as well. Compare with `ls -ldn /host/path` (numeric owner of host dir).\n  \n  **Fix:**\n  ```bash\n  sudo chown 65534:65534 /host/path && sudo chmod 755 /host/path\n  sudo docker restart <name>\n  ```\n  Without this, the container reads config files (world-readable) but writes to state/output files fail silently at cycle end.

## References

- **Viberayd deployment** — See [references/viberayd-deployment.md](references/viberayd-deployment.md) for a complete walkthrough: cloning, fixing the Dockerfile, building, and running the Viberayd proxy subscription daemon on a remote server.
