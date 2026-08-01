# Viberayd Deployment Walkthrough

Deployed **Viberayd** (proxy subscription daemon) on `core-srv` (192.168.4.120) from repo `https://github.com/amirrezaalavi/Viberayd.git`. This is a Go daemon that fetches proxy subscription URLs, tests configs (TCP + TLS), and serves working ones via HTTP.

## What Was Deployed

- **Image:** viberayd:latest (built on-server from source)
- **Container name:** viberayd
- **Restart policy:** unless-stopped
- **Data dir (host):** /opt/viberayd/ → mounted to /work in container
- **Ports:** 8084 (subscription endpoint), 8085 (management API)
- **Config file:** /opt/viberayd/config.toml
- **URLs file:** /opt/viberayd/urls.txt (2 subscription URLs)

## Build Fix Applied

The repo had no `go.sum` (excluded by .gitignore). The original Dockerfile used `go mod download 2>/dev/null || true` which silently failed. Changed to `go mod tidy` before and after `COPY . .`.

## Files Created on Server

**Config** (`/opt/viberayd/config.toml`):
```toml
version = 1

[daemon]
urls_file = "/work/urls.txt"
output_file = "/work/working.txt"
state_file = "/work/state.json"
cycle_sleep = 300
parallel = 5
timeout = 10
depth = "standard"
keep_successful = true
retest_interval = 1800

[http]
enabled = true
port = 8084
sub_path = "/sub"
api_port = 8085
```

**Subscription URLs** (`/opt/viberayd/urls.txt`):
```
https://raw.githubusercontent.com/ALIILAPRO/v2rayNG-Config/main/sub.txt
https://raw.githubusercontent.com/barry-far/V2ray-config/main/All_Configs_base64_Sub.txt
```

## Docker Commands Used

```bash
# Build
sudo docker build --no-cache -t viberayd:latest /tmp/Viberayd

# Stop old, run new
sudo docker rm -f viberayd 2>/dev/null
sudo docker run -d \
  --name viberayd \
  --restart unless-stopped \
  -v /opt/viberayd:/work \
  -p 8084:8084 \
  -p 8085:8085 \
  viberayd:latest
```

## Verification

```bash
# Container status
sudo docker ps --filter name=viberayd

# Logs showed 6,970 configs fetched and being tested
sudo docker logs viberayd --tail 20

# Management API reachable (from agent at 192.168.13.18)
curl -s http://192.168.4.120:8085/api/health
# → {"status":"ok"}

curl -s http://192.168.4.120:8085/api/stats
# → {"failed":0,"total":6970,"unreachable":0,"working":0,...}

# Subscription endpoint
curl -s http://192.168.4.120:8084/sub
# → "no data" (until first test cycle completes)
```

## Volume Permission Fix

The container ran as `nobody:nobody` (uid 65534) but `/opt/viberayd` was owned by `core` (uid 1000). Cycle 1 completed successfully (log: "cycle complete working=3175 failed=486 unreachable=3309") but no `working.txt` or `state.json` were written.

**Fix:** chown the volume mount directory to uid 65534:
```bash
sudo chown 65534:65534 /opt/viberayd
sudo chmod 775 /opt/viberayd
sudo docker restart viberayd
```

After restart, cycle completed in 4m22s and wrote both files:
- `/opt/viberayd/working.txt` — 809 KB (3,412 working configs, base64-encoded)
- `/opt/viberayd/state.json` — 5.6 MB

## Final Results

| Metric | Value |
|--------|-------|
| Working configs | **3,412** |
| Failed | 305 |
| Unreachable | 3,274 |
| Subscription endpoint | HTTP 200 — **1,079,324 bytes** of base64 proxy configs |
| Cycle duration | ~4m22s (post-fix, cached state) |

## Caveats

- 6,970 configs at parallel=5, timeout=10s → first cycle takes 30min-4h
- The /sub endpoint returns 404 + "no data" until at least one working config is found
- Credential `core / Core8orn@` on `core@192.168.4.120` for SSH access
