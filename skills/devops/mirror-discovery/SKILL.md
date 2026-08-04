---
name: mirror-discovery
description: 'Probe a URL to discover what package mirrors it hosts.'
---

# Mirror Discovery

Given a base URL (e.g. `https://mirror.example.com`), discover what package repositories and distros it hosts, then test speed.

## Architecture

Two-phase approach — never rely on a single method:

```
Phase 1: Signature probing (deterministic, 27 paths, parallel)
Phase 2: HTML root scraping (supplemental, catches non-standard layouts)
```

## Phase 1: The Probe Table

For each repo type, probe **deep signature paths** — not directory listings. The Release file, `.db` file, `repomd.xml`, or `APKINDEX.tar.gz` are the only reliable markers. Directory listings (`/ubuntu/`) can return 502 or redirect even when the repo exists.

### Probes (27 parallel, 5s timeout each, body-validated)

| Type | Path | Marker |
|------|------|--------|
| APT (Ubuntu) | `/{prefix}/dists/{suite}/Release` | File contains `Origin:`, `Components:`, `Architectures:` |
| APT (Debian) | `/{prefix}/dists/{suite}/Release` | Same format |
| Arch | `/archlinux/core/os/x86_64/core.db` | gzipped tar |
| Alpine | `/alpine/v{ver}/main/{arch}/APKINDEX.tar.gz` | gzipped tar |
| EPEL | `/epel/{ver}/Everything/{arch}/repodata/repomd.xml` | XML with `<repomd>` |
| OpenSUSE | `/opensuse/tumbleweed/repo/oss/repodata/repomd.xml` | XML with `<repomd>` |
| Docker | `/v2/` | 200 or 401 |

### Probe paths by distro (as of mid-2026)

```go
// APT Ubuntu (active LTS releases)
"/ubuntu/dists/resolute/Release"   // 26.04 LTS
"/ubuntu/dists/noble/Release"      // 24.04 LTS
"/ubuntu/dists/jammy/Release"      // 22.04 LTS

// APT Debian
"/debian/dists/forky/Release"      // 14 (testing)
"/debian/dists/trixie/Release"     // 13 (stable)
"/debian/dists/bookworm/Release"   // 12 (oldstable)

// Arch
"/archlinux/core/os/x86_64/core.db"

// Alpine
"/alpine/v3.24/main/x86_64/APKINDEX.tar.gz"  // latest
"/alpine/v3.23/main/x86_64/APKINDEX.tar.gz"
"/alpine/edge/main/x86_64/APKINDEX.tar.gz"

// EPEL (consistent across ALL mirrors — the only RPM family with stable paths)
"/epel/10/Everything/x86_64/repodata/repomd.xml"
"/epel/9/Everything/x86_64/repodata/repomd.xml"
"/epel/8/Everything/x86_64/repodata/repomd.xml"

// OpenSUSE
"/opensuse/tumbleweed/repo/oss/repodata/repomd.xml"

// Docker Registry
"/v2/"

// PyPI (PEP 503 simple index)
"/simple/"
"/pypi/simple/"

// npm registry
"/-/v1/search?text=test&size=1"
"/npm/-/v1/search?text=test&size=1"

// Composer / Packagist
"/packages.json"
"/composer/packages.json"
```

Total: **27 parallel probes** (5s timeout each).

### RPM paths that work

After live testing against 4 reference mirrors (Rackspace, MIT, TUNA, xTom), these paths were **confirmed working**:

| Type | Path | Verified on |
|------|------|-------------|
| Rocky Linux | `/{ver}/BaseOS/{arch}/os/repodata/repomd.xml` | Rackspace ✅, xTom ✅ |
| AlmaLinux | `/{ver}/BaseOS/{arch}/os/repodata/repomd.xml` | Rackspace ✅, xTom ✅ |

Last 3 versions (10, 9, 8) all confirmed 200 with valid `<repomd>` XML on both mirrors.

```go
// Rocky Linux (last 3 versions)
"/rocky/10/BaseOS/x86_64/os/repodata/repomd.xml"
"/rocky/9/BaseOS/x86_64/os/repodata/repomd.xml"
"/rocky/8/BaseOS/x86_64/os/repodata/repomd.xml"

// AlmaLinux (last 3 versions)
"/almalinux/10/BaseOS/x86_64/os/repodata/repomd.xml"
"/almalinux/9/BaseOS/x86_64/os/repodata/repomd.xml"
"/almalinux/8/BaseOS/x86_64/os/repodata/repomd.xml"
```

**Key insight**: Rocky and AlmaLinux package repos live at `BaseOS/{arch}/**os/**/repodata/repomd.xml` — the `/os/` segment is critical and easy to forget. Without it, the probe returns 404 (tested: `BaseOS/x86_64/repodata/repomd.xml` without `/os/` → 404 on both Rackspace and xTom).

### Paths that still don't work reliably

| Distro | Status | Reason |
|--------|--------|--------|
| CentOS Stream | ❌ No reliable path | Varies too much between mirrors; official `mirror.stream.centos.org` has yet another layout |
| Fedora | ❌ No reliable path | General-purpose mirrors (Rackspace, MIT, TUNA, xTom) only carry Fedora ISOs, not package repos. The official Fedora mirror network (`dl.fedoraproject.org`) is behind a CDN and has different paths. |
| EPEL | ✅ Works | The one exception — always at `/{ver}/Everything/{arch}/repodata/repomd.xml` across ALL mirrors |

For CentOS Stream and Fedora, HTML scraping (Phase 2) is still the right tool — if the root page links to `/centos-stream/` or `/fedora/`, the name is noted but no deterministic probe exists yet.

## Phase 2: HTML Root Scraping

When the root URL returns 200 with HTML, extract all `<a href="...">` links. Check if any path segment matches known distro names. This catches non-standard layouts without blind probing.

```go
knownDistros := []string{
    "ubuntu", "debian", "centos", "centos-stream", "fedora",
    "alpine", "archlinux", "rocky", "almalinux", "epel",
    "opensuse", "gentoo", "freebsd",
}
```

Only distro names that **actually appear in the root HTML** get probed with their signature paths.

### Root page types observed

| Type | Example | How to handle |
|------|---------|--------------|
| Plain Apache listing | Rackspace | Easy — links in `<li><a href="distro/">` |
| Custom styled page with links | xTom, MIT | Same pattern, different CSS |
| JS-rendered SPA | TUNA | Check `/legacy_index` endpoint, or fall back to probes only |
| Redirect to marketing | ArvanCloud | Don't follow root redirect — probe paths independently |
| Custom dashboard | Chabokan | Links in root HTML → probe each |

## Speed Testing

### Rule: only test apt + docker

All repos on the same mirror share the same IP/network path. Testing every detected type is redundant. Only the bandwidth-heavy types matter:

| Priority | Test | Target | Method |
|----------|------|--------|--------|
| 1 | APT | `{prefix}/ls-lR.gz` (1-50 MB) | Download, track throughput |
| 2 | Docker | `/v2/` blob layer (10-100 MB) | Download, track throughput |
| Fallback | Any detected | The signature file itself (50-500 KB, less accurate) | Download, track throughput |

All other detected types (Arch, Alpine, EPEL, OpenSUSE, PyPI, npm, Composer) **do not get a speed test** — the APT or Docker result is representative of the mirror's network performance.

### Speed test algorithm

1. GET url with context timeout
2. Read in 64KB chunks (NOT 512KB — smaller buffer avoids burst aliasing)
3. Stop when: EOF, OR 2s elapsed with >=1MB downloaded (early-exit), OR timeout
4. Require >=100KB minimum download — less than that is not a meaningful sample
5. `speedMBps = (downloadedBytes / 1024 / 1024) / elapsedSeconds`

### ForceFull vs early-exit

| Mode | When to use | Behavior |
|------|-------------|----------|
| **Early-exit** (default) | Pure speed measurement | Stop after 2s + 1MB. Fast, accurate throughput sample. Does NOT drain the body. |
| **ForceFull** | Need to verify the file exists completely | Read to EOF. Slower but confirms the file is whole. Use for package existence checks. |

The Go function signature is:
```go
func MeasureThroughput(ctx context.Context, resp *http.Response, opts SpeedOpts) (SpeedResult, error)
```
where `SpeedOpts{ForceFull: true}` forces full download, `SpeedOpts{MinSampleBytes: N, MinSampleDuration: D}` tunes the early-exit threshold.

## Common Pitfalls

### 1. Directory listings lie
`/ubuntu/` might return 502 (Chabokan) even though `/ubuntu/dists/resolute/Release` works fine. Always probe deep signature paths, not directory listings.

### 2. Root redirects are irrelevant
ArvanCloud root (301 to marketing page) tells you nothing about what repos it hosts. Never follow root redirect for content discovery. Probe paths independently.

### 3. Docker registries hide on subdomains
`docker.arvancloud.ir` exists but is a different hostname from `mirror.arvancloud.ir`. The `/v2/` probe on the main host won't find it. The user must provide the Docker mirror URL separately, or you can check common subdomains (`docker.{base}`, `registry.{base}`).

### 4. Repo paths vary per mirror operator
Same distro, different layout:
- `https://mirror.example.com/ubuntu/dists/noble/Release` — common
- `https://mirror.example.com/archive/ubuntu/dists/noble/Release` — also exists

The probe table covers the most common prefix patterns. For edge cases, HTML scraping + suite discovery (probing multiple suites under the same prefix) usually finds it.

### 5. EPEL is the only predictable RPM family
CentOS, Fedora, Rocky, AlmaLinux all have version-specific paths that vary by mirror. Only EPEL consistently uses `/{ver}/Everything/{arch}/repodata/repomd.xml`.

### 6. Suite names change over time
- Ubuntu 24.10 (oracular) was already EOL (404) as of mid-2026
- Debian: trixie (13) is now stable, forky (14) is testing
- Alpine: v3.25 not yet out as of mid-2026
- Ubuntu 25.04 (plucky) was removed from probe table in favour of resolute (26.04 LTS)
Always check current versions when setting up probe tables. The `references/probe-data-july-2026.md` file tracks what was confirmed live.

### 7. Suite lifecycle management
Probe tables decay. Treat the suite list as a **living configuration** that needs periodic refresh:
- When Debian releases a new stable, the old testing becomes stable and a new testing name appears (forky 14 appeared mid-2026)
- Ubuntu non-LTS releases go EOL fast (oracular 24.10 was already 404 by July 2026)
- Alpine and EPEL add new major versions yearly
- Strategy: check the live Release file once per session to confirm versions, don't hardcode dates

### 8. Go HTTP Client transparently decompresses gzip (critical)
Go's default HTTP client (`DisableCompression: false`) automatically decompresses gzip-encoded responses. The body your code sees is already decompressed — so checking for gzip magic bytes (`0x1f 0x8b`) **always fails**.

Symptoms: Arch Linux `core.db` returns 200 but `validateGzip()` returns false. Alpine `APKINDEX.tar.gz` same. The probe table entry exists but never matches. This was discovered when Rackspace's `core.db` was confirmed gzip by `file` but Go code saw decompressed data.

Fix: set `DisableCompression: true` on the HTTP Transport:
```go
client := &http.Client{
    Transport: &http.Transport{
        DisableCompression: true,  // preserve raw bytes
    },
}
```
This also gives accurate speed measurements (raw network throughput, not decompressed). After fixing, Arch detection started working on Rackspace and other mirrors.

### 9. Some mirrors return 200 with empty body on any path
Rasanegar (`mirror.rasanegaar.com`) returns 200 with empty body for every path. This acts as a catch-all stub. Body validation functions handle this correctly (empty body fails all checks), but it wastes probing time. If all probes return 200 but none validate, test a known-bad path (`/nonexistent-file-xyz`) — if that also 200s, it's a catch-all.

### 10. Institutional mirrors prefix everything under a subdirectory

Some mirrors (especially universities) don't serve repos at the domain root. IUT (`repo.iut.ac.ir`) hosts everything under `/repo/`: actual paths are `/repo/archlinux/core/os/x86_64/core.db`, not `/archlinux/core/os/x86_64/core.db`. The probe table only checks root-level paths and misses these entirely.

Symptoms: apt (ubuntu/debian) is detected because the mirror operator symlinked `/ubuntu` → `/repo/ubuntu` at root, but Arch, Alpine, OpenSUSE are not symlinked — they're only accessible under the prefix. In IUT's case, the root HTML page links to `/repo/` but the engine's HTML scraping only extracts first-level directory names, not second-level prefixed paths.

Mitigation: after initial probes complete, check if any scraped root links look like prefix directories (e.g., `/repo/`, `/mirror/`, `/mirrors/`) and re-probe all signatures under each prefix. Also probe common prefixes unconditionally.

### 11. EPEL can be unreachable even when listed
Rasanegar claims EPEL-only in the catalogs but returns 503 for `/epel/9/Everything/x86_64/repodata/repomd.xml`. Mirrors break. Always verify 200 on the signature path, don't trust catalog metadata.

## Go implementation reference

The algorithms described here are implemented in the `mirava-core` Go library at `pkg/discovery/`:

| File | Purpose |
|------|---------|
| `pkg/discovery/discovery.go` | `Engine.Discover()` — probes, scraping, enrichment; `Engine.TestSpeed()` — speed measurement orchestration |
| `pkg/discovery/probes.go` | Probe table (21 signatures), body validation functions, HTML href extraction |
| `pkg/discovery/discovery_test.go` | 28 offline tests using `httptest` |
| `pkg/speedtest.go` | Shared `MeasureThroughput()` — the single download loop all backends should use |
| `mirava.go` | Top-level `mirava.Discover()` and `mirava.DiscoverAndBenchmark()` |

The existing backends (`pkg/apt.go`, `pkg/npm.go`, etc.) are **untouched** — backward compatibility is maintained.

### Key Go-specific gotchas from the implementation

1. **`DisableCompression: true`** is required on the engine's HTTP client, otherwise Go's net/http transparently decompresses gzip responses and breaks `validateGzip`. Old backends use separate clients with default compression.
2. **`go.mod`** might specify `go 1.26.0` which is unreleased. If building locally fails with `toolchain not available`, downgrade to `go 1.24.0` — no 1.26-specific features were used.
3. **`resp.Body.Read()` blocks regardless of context.** The `ctx.Done()` select branch only fires between Read() calls. When implementing timeouts, ensure the server sends data in small chunks with Flush() so Read() returns between chunks.
4. **Body validation reads first 64KB only** via `io.LimitReader`. This is enough for signature detection (gzip magic, Release headers, XML root) but not for full content validation.

## Quick diagnostic (bash)

The `scripts/verify-mirror.sh` script probes a mirror using curl with the same probe table. No Go needed:

```bash
bash scripts/verify-mirror.sh https://mirror.example.com
```

Output shows HTTP status codes for each probe path — 200 means detected.

## References

- `references/probe-data-july-2026.md` — Raw probe results from 6 mirrors with version verification data and session-level change tracking.
- `scripts/verify-mirror.sh` — Bash script for quick mirror probing without Go.

## Verification

After a probe returns 200, **validate the content format** before declaring a match:

| Type | Validation |
|------|-----------|
| APT Release | Body starts with `Origin:`, contains `Components:` |
| Arch `.db` | First bytes are gzip magic (`1f 8b`) |
| Alpine APKINDEX | First bytes are gzip magic |
| EPEL/Fedora/OpenSUSE `repomd.xml` | Parses as XML with `<repomd>` root |
| Docker `/v2/` | Status 200 or 401 (401 = auth required, but endpoint exists) — body is valid JSON |
| PyPI `/simple/` | Body contains `<a href` with a non-http relative path (avoids false positives on generic HTML) |
| npm search | Body JSON contains `"objects"` array |
| Composer `packages.json` | Body JSON contains `"packages"` or `"metadata-url"` |

## Real-world examples from probing (July 2026)

| Mirror | Phase 1 catches | Phase 2 catches | Notes |
|--------|----------------|----------------|-------|
| `mirror2.chabokan.net` | apt ubuntu, docker | npm, composer, pypi (from root links) | `/ubuntu/` returns 502, deep paths work. Has npm at `/npm/`, PyPI at `/pypi/simple/`, Composer at `/composer/` |
| `mirror.arvancloud.ir` | apt ubuntu | (redirects, no root page) | Docker on separate `docker.arvancloud.ir` subdomain |
| `hkg.mirror.rackspace.com` | apt ubuntu+debian, arch, epel | 45+ links (centos, fedora, rockylinux, etc.) | Best HTML scraping target |
| `mirrors.mit.edu` | apt ubuntu+debian, arch, epel | 25+ links | Custom HTML table, still scrapable |
| `mirrors.tuna.tsinghua.edu.cn` | apt ubuntu+debian, arch, alpine, epel, opensuse | 100+ links (via legacy_index) | JS SPA root; `/legacy_index` works |
| `mirrors.xtom.ee` | apt ubuntu+debian, arch, alpine, epel | ~30 links from styled HTML | Has docker-ce apt repo (package), not Docker registry |
