#!/usr/bin/env bash
# service_inventory.sh — read-only service inventory for a remote Linux host.
# Usage: ./service_inventory.sh [user@]host
# Covers every service layer on a typical Debian/Docker/K3s/Incus box:
#   systemd units, listening ports, docker containers, k3s workloads, incus containers, disk/mem.
# Never mutates the target — safe to run any time.
set -uo pipefail
HOST="${1:?usage: $0 [user@]host}"

echo "=== UPTIME ==="
ssh -o BatchMode=yes "$HOST" 'uptime'

echo "=== SYSTEMD RUNNING ==="
ssh -o BatchMode=yes "$HOST" 'systemctl list-units --type=service --state=running --no-pager --no-legend | awk "{print \$1}"'

echo "=== SYSTEMD ENABLED ==="
ssh -o BatchMode=yes "$HOST" 'systemctl list-unit-files --type=service --state=enabled --no-pager --no-legend | awk "{print \$1}"'

echo "=== LISTENING PORTS ==="
# process names need root; fall back to plain ss if sudo unavailable
ssh -o BatchMode=yes "$HOST" 'sudo ss -tlnp 2>/dev/null || ss -tlnp 2>/dev/null'

echo "=== DOCKER CONTAINERS ==="
ssh -o BatchMode=yes "$HOST" 'sudo docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}" 2>&1 | head -40'

echo "=== K3S NODES ==="
ssh -o BatchMode=yes "$HOST" 'sudo k3s kubectl get nodes -o wide 2>/dev/null | head -10'

echo "=== K3S PODS (all ns) ==="
ssh -o BatchMode=yes "$HOST" 'sudo k3s kubectl get pods -A -o wide 2>/dev/null | head -40'

echo "=== K3S SERVICES (all ns) ==="
ssh -o BatchMode=yes "$HOST" 'sudo k3s kubectl get svc -A 2>/dev/null | head -40'

echo "=== INCUS CONTAINERS ==="
ssh -o BatchMode=yes "$HOST" 'incus list 2>&1 | head -30'

echo "=== DISK ==="
ssh -o BatchMode=yes "$HOST" 'df -h / 2>/dev/null | head -5'

echo "=== MEM ==="
ssh -o BatchMode=yes "$HOST" 'free -h'

echo "=== DONE ==="
