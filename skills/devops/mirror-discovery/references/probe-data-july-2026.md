## Probe table changes (this session)

| Change | Old | New | Reason |
|--------|-----|-----|--------|
| Ubuntu removal | plucky (25.04), focal (20.04) | — | User decision: keep only LTS + latest interim |
| Ubuntu addition | — | resolute (26.04) | New LTS, confirmed 200 on mirrors |
| Debian addition | — | forky (14) | New testing suite, confirmed 200 |
| Alpine trim | v3.20, v3.21, v3.22 | — | User decision: keep only latest + edge |
| Added PyPI | — | `/simple/`, `/pypi/simple/` | User request; confirmed on Chabokan |
| Added npm | — | `/-/v1/search`, `/npm/-/v1/search` | User request; confirmed on Chabokan |
| Added Composer | — | `/packages.json`, `/composer/packages.json` | User request; confirmed on Chabokan |
| Added Rocky Linux | — | `/rocky/{10,9,8}/BaseOS/x86_64/os/repodata/repomd.xml` | Confirmed on Rackspace + xTom; key: `/os/` in path |
| Added AlmaLinux | — | `/almalinux/{10,9,8}/BaseOS/x86_64/os/repodata/repomd.xml` | Confirmed on Rackspace + xTom; same path pattern |

# Session Probe Data (July 2026)

Raw probe results from 6 mirrors, used to build the discovery probe table.

## mirror2.chabokan.net

| Probe | Result |
|-------|--------|
| `/` | 200 HTML (links: ubuntu, debian, pypi, npm, composer, docker) |
| `/ubuntu/dists/resolute/Release` | 200 (26.04 LTS ✅) |
| `/ubuntu/dists/noble/Release` | 200 |
| `/ubuntu/dists/jammy/Release` | 200 |
| `/ubuntu/dists/bookworm/Release` | 502 (no Debian on this prefix) |
| `/debian/dists/trixie/Release` | 200 ✅ |
| `/v2/` | 200 `{"name":"Chabok Mirror Docker Registry"}` ✅ |
| `/ubuntu/` | **502** — directory listing broken, but deep paths work |
| `/pypi/simple/` | 200 (PyPI PEP 503 simple index ✅) |
| `/npm/-/v1/search` | 200 (npm search API ✅) |
| `/composer/packages.json` | 200 (Composer metadata ✅) |

Key lesson: `/ubuntu/` returns 502 but deep apt paths work. Never trust directory listings.

## mirror.arvancloud.ir

| Probe | Result |
|-------|--------|
| `/` | 301 → `https://www.arvancloud.ir/dev/linux-repository` |
| `/ubuntu/dists/resolute/Release` | 200 ✅ |
| `/ubuntu/dists/noble/Release` | 200 |
| `/ubuntu/dists/jammy/Release` | 200 |
| `/ubuntu/dists/focal/Release` | 200 |
| `/v2/` | 503 (Docker at `docker.arvancloud.ir` — separate subdomain) |
| `/centos/` | 404 (mirror doesn't carry CentOS despite README claim) |
| `/ubuntu/ls-lR.gz` | 200 11.9MB ✅ (speed test target) |

Key lessons: root redirects ≠ mirror content; Docker often on separate subdomain.

## hkg.mirror.rackspace.com

| Probe | Result |
|-------|--------|
| `/` | 200 Apache listing → 45+ links |
| `/ubuntu/dists/noble/Release` | 200 ✅ |
| `/debian/dists/bookworm/Release` | 200 ✅ |
| `/archlinux/core/os/x86_64/core.db` | 200 ✅ |
| `/archlinux/core/os/x86_64/core.db` | 200 ✅ |
| `/rocky/10/BaseOS/x86_64/os/repodata/repomd.xml` | 200 ✅ |
| `/rocky/9/BaseOS/x86_64/os/repodata/repomd.xml` | 200 ✅ |
| `/rocky/8/BaseOS/x86_64/os/repodata/repomd.xml` | 200 ✅ |
| `/almalinux/10/BaseOS/x86_64/os/repodata/repomd.xml` | 200 ✅ |
| `/almalinux/9/BaseOS/x86_64/os/repodata/repomd.xml` | 200 ✅ |
| `/almalinux/8/BaseOS/x86_64/os/repodata/repomd.xml` | 200 ✅ |
| `/epel/9/Everything/x86_64/repodata/repomd.xml` | 200 ✅ |
| Root links include: | CPAN, CentOS, FreeBSD, almalinux, archlinux, centos-stream, debian, docker-ce, epel, fedora, gentoo, opensuse, rocky, slackware, ubuntu |

Key lesson: best HTML scraping target. Plain Apache directory listing.

## mirrors.mit.edu

| Probe | Result |
|-------|--------|
| `/` | 200 custom HTML with project table |
| `/ubuntu/dists/noble/Release` | 200 ✅ |
| `/debian/dists/bookworm/Release` | 200 ✅ |
| `/archlinux/core/os/x86_64/core.db` | 200 ✅ |
| `/epel/9/Everything/x86_64/repodata/repomd.xml` | 200 ✅ |
| Root HTML: | Custom table with 25+ projects |

## mirrors.tuna.tsinghua.edu.cn

| Probe | Result |
|-------|--------|
| `/` | 200 JS SPA (use `/legacy_index` for plain HTML) |
| `/ubuntu/dists/noble/Release` | 200 ✅ |
| `/debian/dists/bookworm/Release` | 200 ✅ |
| `/archlinux/core/os/x86_64/core.db` | 200 ✅ |
| `/alpine/v3.20/main/x86_64/APKINDEX.tar.gz` | 200 ✅ |
| `/epel/9/Everything/x86_64/repodata/repomd.xml` | 200 ✅ |
| `/opensuse/tumbleweed/repo/oss/repodata/repomd.xml` | 200 ✅ |
| `/legacy_index` | 100+ href links |

Key lesson: JS SPA sites may need a `/legacy_index` fallback.

## mirrors.xtom.ee

| Probe | Result |
|-------|--------|
| `/` | 200 styled HTML with ~30 links |
| `/ubuntu/dists/resolute/Release` | 200 ✅ |
| `/ubuntu/dists/plucky/Release` | 200 ✅ |
| `/ubuntu/dists/noble/Release` | 200 |
| `/ubuntu/dists/jammy/Release` | 200 |
| `/debian/dists/forky/Release` | 200 ✅ (Debian 14) |
| `/debian/dists/trixie/Release` | 200 ✅ |
| `/debian/dists/bookworm/Release` | 200 |
| `/archlinux/core/os/x86_64/core.db` | 200 ✅ |
| `/alpine/v3.24/main/x86_64/APKINDEX.tar.gz` | 200 ✅ |
| `/epel/10/Everything/x86_64/repodata/repomd.xml` | 200 ✅ |
| `/v2/` | 404 (has docker-ce apt repo, not Docker registry) |
| Root links: | almalinux, alpine, archlinux, centos-stream, debian, docker-ce, epel, fedora, rocky, ubuntu |

## Live subagent test results (July 2026 session)

Run against real mirrors from the MiravaOrg/Mirava catalog using the Go probe binary. Tests verify both the discovery algorithm and the Go implementation.

| Mirror | Types Detected | Speed | Notes |
|--------|---------------|-------|-------|
| `repo.iut.ac.ir` (Iran) | apt ubuntu (resolute, noble, jammy), apt debian (trixie, bookworm) | 0.86 MB/s | Missing Alpine, Arch, OpenSUSE despite catalog claims. Debian forky not found. |
| `mirror.freedif.org` (Singapore) | apt ubuntu (resolute, noble, jammy), apt debian (forky, trixie, bookworm), pacman, opensuse, alpine | 5.5 MB/s | Best match. All claimed types detected. Fast Singapore mirror — good test target. |
| `mirror.mobinhost.com` (Iran) | apt ubuntu (resolute, noble, jammy), apt debian (forky, trixie, bookworm), pacman, alpine, epel | — | Multi-package. No false positives. |
| `mirrors.pardisco.co` (Iran) | apt ubuntu (resolute, noble, jammy), apt debian (forky, trixie, bookworm), alpine, docker | 3.8 MB/s | Docker detected via `/v2/`. PyPI and npm claimed but not found. |
| `mirror.rasanegaar.com` (Iran) | **nothing** (EPEL claimed but 503, catch-all empty 200) | — | Catalog says EPEL-only but all paths return 503. Catch-all returns 200 with empty body on any path — correctly rejected by body validation. |
| `docker.iranserver.com` (Iran) | **docker only** | 1.35 MB/s | Edge case: single-type mirror. No false positives on other types. |

### Key findings from live tests

1. **Catalogs lie.** Mirrors claim more than they serve. IUT claimed Alpine/Arch/OpenSUSE but only apt worked. Pardisco claimed PyPI/npm but only apt/alpine/docker worked.
2. **Single-type edge cases work.** `docker.iranserver.com` correctly detected only docker.
3. **Catch-all servers handled.** Rasanegar's 200+empty-body catch-all rejected by body validation.
4. **DisableCompression fix confirmed.** After setting `DisableCompression: true`, Rackspace Arch `core.db` detected correctly.
5. **FreeDif (Singapore) = best test mirror.** Fast, comprehensive, globally accessible.
6. **Rocky + AlmaLinux paths confirmed.** Both respond at `BaseOS/x86_64/os/repodata/repomd.xml` with `/os/` in the path. Without `/os/`, 404.
7. **Rocky + Alma work on Rackspace and xTom** — both carry versions 8, 9, 10.

| Suite | Status |
|-------|--------|
| Ubuntu resolute (26.04 LTS) | ✅ 200 — `Origin: Ubuntu`, `Suite: resolute`, `Version: 26.04` |
| Ubuntu plucky (25.04) | ✅ 200 (removed from active probe table by user request) |
| Ubuntu noble (24.04 LTS) | ✅ 200 |
| Ubuntu jammy (22.04 LTS) | ✅ 200 |
| Ubuntu focal (20.04 LTS) | ❌ removed from probe table (user decision) |
| Ubuntu oracular (24.10) | ❌ 404 (EOL) |
| Debian forky (14) | ✅ 200 |
| Debian trixie (13) | ✅ 200 |
| Debian bookworm (12) | ✅ 200 |
| Alpine v3.24 | ✅ 200 (latest) |
| Alpine v3.23 | ✅ 200 |
| Alpine v3.22 | ✅ 200 (removed from active probe table by user request) |
| Alpine v3.21 | ✅ 200 (removed) |
| Alpine v3.20 | ✅ 200 (removed) |
| Alpine v3.25 | ❌ 404 (not yet released) |
| EPEL 10 | ✅ 200 (latest) |
| EPEL 9 | ✅ 200 |
| EPEL 11 | ❌ 404 (not yet released) |
| Rocky 10 | ✅ 200 (Rackspace, xTom) |
| Rocky 9 | ✅ 200 |
| Rocky 8 | ✅ 200 |
| AlmaLinux 10 | ✅ 200 (Rackspace, xTom) |
| AlmaLinux 9 | ✅ 200 |
| AlmaLinux 8 | ✅ 200 |
