#!/usr/bin/env bash
# verify-mirror.sh — Probe a mirror URL for available repos
# Usage: ./verify-mirror.sh <base-url>
# Example: ./verify-mirror.sh https://mirror.example.com
set -euo pipefail

BASE="${1%/}"
: "${BASE:?Usage: verify-mirror.sh <base-url>}"

probe() {
    local path="$1" label="$2"
    local url="${BASE}${path}"
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || echo "TIMEOUT")
    printf "  %-8s %s\n" "$code" "$label"
    [ "$code" = "200" ] || [ "$code" = "401" ]
}

echo "=== Probe: $BASE ==="
echo ""

echo "--- APT (Ubuntu) ---"
probe "/ubuntu/dists/resolute/Release" "resolute (26.04)"
probe "/ubuntu/dists/noble/Release"    "noble (24.04)"
probe "/ubuntu/dists/jammy/Release"    "jammy (22.04)"

echo "--- APT (Debian) ---"
probe "/debian/dists/forky/Release"    "forky (14)"
probe "/debian/dists/trixie/Release"   "trixie (13)"
probe "/debian/dists/bookworm/Release" "bookworm (12)"

echo "--- Arch ---"
probe "/archlinux/core/os/x86_64/core.db" "archlinux"

echo "--- Alpine ---"
probe "/alpine/v3.24/main/x86_64/APKINDEX.tar.gz" "v3.24"
probe "/alpine/v3.23/main/x86_64/APKINDEX.tar.gz" "v3.23"
probe "/alpine/edge/main/x86_64/APKINDEX.tar.gz"  "edge"

echo "--- EPEL ---"
probe "/epel/10/Everything/x86_64/repodata/repomd.xml" "epel 10"
probe "/epel/9/Everything/x86_64/repodata/repomd.xml"  "epel 9"

echo "--- Rocky Linux ---"
probe "/rocky/10/BaseOS/x86_64/os/repodata/repomd.xml" "rocky 10"
probe "/rocky/9/BaseOS/x86_64/os/repodata/repomd.xml"  "rocky 9"

echo "--- AlmaLinux ---"
probe "/almalinux/10/BaseOS/x86_64/os/repodata/repomd.xml" "alma 10"
probe "/almalinux/9/BaseOS/x86_64/os/repodata/repomd.xml"  "alma 9"

echo "--- OpenSUSE ---"
probe "/opensuse/tumbleweed/repo/oss/repodata/repomd.xml" "tumbleweed"

echo "--- Docker ---"
probe "/v2/" "docker registry"

echo "--- PyPI ---"
probe "/simple/"        "pypi (/simple/)"
probe "/pypi/simple/"   "pypi (/pypi/simple/)"

echo "--- npm ---"
probe "/-/v1/search?text=test&size=1"       "npm (/-/v1/search)"
probe "/npm/-/v1/search?text=test&size=1"   "npm (/npm/-/v1/search)"

echo "--- Composer ---"
probe "/packages.json"          "composer (/packages.json)"
probe "/composer/packages.json" "composer (/composer/packages.json)"

echo ""
echo "--- done ---"
