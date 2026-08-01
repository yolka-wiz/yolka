---
name: mirror-probe-discovery
description: "Probe a mirror URL to discover repos and test speed."
category: devops
---

Given any mirror URL (e.g. `https://hkg.mirror.rackspace.com`), discover what package/container repo types it serves and measure their speed and availability.

## Two-Phase Discovery Algorithm

### Phase 1: Direct Signature Probes

Probe known paths that are **diagnostic** of each ecosystem:

| Probe Path | Detected Type | Validation |
|-----------|---------------|------------|
| `{prefix}/dists/{suite}/Release` | APT (Ubuntu/Debian) | Check `Origin:`, `Components:`, `Architectures:` in body |
| `/archlinux/core/os/x86_64/core.db` | Arch/Pacman | Returns gzip tar |
| `/alpine/v{VERSION}/main/x86_64/APKINDEX.tar.gz` | Alpine | Returns gzip tar |
| `/epel/{VERSION}/Everything/x86_64/repodata/repomd.xml` | EPEL | XML `<repomd>` root |
| `/opensuse/tumbleweed/repo/oss/repodata/repomd.xml` | OpenSUSE | XML repomd |
| `/v2/` | Docker Registry | 200/401 = detected |
| `/simple/` or `/pypi/simple/` | PyPI | HTML with `<a>` links |
| `/-/v1/search?text=test&size=1` | npm | JSON `{"objects":[...]}` |
| `/packages.json` | Composer | JSON `{"packages":...}` |
| `/config.json` | Cargo Sparse Index | JSON with `dl` field |
| `/github.com/gorilla/mux/@v/list` | Go Proxy | Version strings, one per line |

### Phase 2: Root HTML Scraping

Many mirrors list repos in root page HTML: Apache dir listings (Rackspace), custom tables (MIT), styled links (xTom), JS pages with `/legacy_index` fallback (TUNA). Extract href paths, match against known distro prefixes (ubuntu, debian, centos, fedora, alpine, archlinux, rocky, epel, opensuse).

### Phase 3: Merge

For each distro name found in Phase 2 that has a signature probe, run it to confirm.

## Repo Type Characteristics

### Consistent across mirrors
- **APT**: `{prefix}/dists/{suite}/Release` — works on all tested mirrors
- **Arch**: `/archlinux/core/os/x86_64/core.db` — Rackspace, MIT, TUNA, xTom
- **Alpine**: `/alpine/v{VERSION}/main/x86_64/APKINDEX.tar.gz` — TUNA, xTom
- **EPEL**: `/epel/{VERSION}/Everything/x86_64/repodata/repomd.xml` — all 4 tested
- **OpenSUSE**: `/opensuse/tumbleweed/repo/oss/repodata/repomd.xml` — TUNA

### Inconsistent (use HTML scraping)
CentOS, Fedora, Rocky, AlmaLinux — version paths vary wildly between mirrors. No single probe path. EPEL is the only RPM exception.

## APT Prefix Discovery

The distro prefix is unknown from base URL alone. Probe candidates in parallel: `""`, `/ubuntu`, `/debian`, `/ubuntu/archive`, `/archive/ubuntu` with suites `noble`, `jammy`, `bookworm`, `bullseye` (~32 probes, ~5s).

## Speed Test Method

Read body in 64KB chunks. Stop at EOF, or >= 1MB AND >= 2s (early exit), or timeout. Require >= 100KB minimum (below is TCP slow-start noise). Rate = (bytes / 1024 / 1024) / seconds.

| Type | Best Target | Typical Size |
|------|------------|-------------|
| APT | `{prefix}/ls-lR.gz` | 1-50 MB |
| Arch | `{prefix}/core/os/x86_64/core.db` | 1-20 MB |
| Docker | `/v2/library/ubuntu/blobs/{digest}` | 10-100 MB |
| Alpine | `/alpine/v3.20/main/x86_64/APKINDEX.tar.gz` | 1-5 MB |

## Known Edge Cases

- **Chabokan**: Root is HTML. Dir paths 502 but deep apt works. Docker at `/v2/`. Non-standard repo paths.
- **ArvanCloud**: Root 301 -> marketing page. Docker on separate subdomain. Apt with 11.9MB `ls-lR.gz`.
- **Docker registries** often on separate subdomains, not discoverable from main URL.
- Don't trust directory listings. Don't follow root redirects.

## Pitfalls

1. PyPI version comparison is lexicographic — `"1.9.0" > "1.10.0"`. Use semver.
2. Speed ratings differ per backend — normalize to raw MB/s.
3. Non-standard paths: PyPI at `/pypi/simple/`, Alpine with version in path.
4. JS-only root pages may need `/legacy_index` fallback (TUNA).
5. RPM repos (except EPEL) are inconsistently structured — use HTML scraping.
