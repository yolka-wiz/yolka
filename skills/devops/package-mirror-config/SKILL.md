---
name: package-mirror-config
description: "Wire fast Aliyun mirrors into Dockerfiles and installs."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mirror, aliyun, apt, pip, docker, deb822, container]
    related_skills: [mirror-discovery]
---

# Package Mirror Configuration

Making installs fast from Iran (or any region where upstream CDNs are slow)
by wiring package managers to mirror hosts inside Dockerfiles, provisioning
scripts, and CI. Discovery of what a mirror hosts is a separate skill
(`mirror-discovery`); this one is about WRITING the config correctly.

## When to Use

- User says "installation took too long, use aliyun mirrors".
- Writing a Dockerfile / reinstall script for an Iran-based user.
- Any container whose apt/pip pulls from default upstream.

## Verification BEFORE writing config (deep-path probing)

Never trust a mirror root page (often 502 or redirect). Probe deep signature
paths, then verify the SPECIFIC package exists:

```bash
# 1. Suite Release files
curl -s -o /dev/null -w "%{http_code}" "https://mirrors.aliyun.com/ubuntu/dists/noble/Release"
#    also probe: noble-security, noble-updates, noble-backports

# 2. Component index — Release 200 does NOT mean your package is present!
curl -s -o /tmp/p.gz "https://mirrors.aliyun.com/ubuntu/dists/noble/universe/binary-amd64/Packages.gz"
zcat /tmp/p.gz | grep -c "^Package: qt6-base-dev$"    # 1 = present
```

Key gotcha (2026-08-05): `qt6-base-dev` is **0 in noble/main, 1 in
noble/universe**. Qt6 dev packages live in universe — check the right
component, or apt install fails after a "successful" probe.

PyPI: `curl -s -o /dev/null -w "%{http_code}" "https://mirrors.aliyun.com/pypi/simple/pillow/"` → 200.

## Ubuntu 24.04+ deb822 sources (not sources.list)

Ubuntu 24.04+ uses `/etc/apt/sources.list.d/ubuntu.sources` (deb822 format);
the old `sources.list` path is gone. Write it in a RUN step BEFORE any
apt-get:

```dockerfile
RUN printf '%s\n' \
    'Types: deb' \
    'URIs: https://mirrors.aliyun.com/ubuntu/' \
    'Suites: noble noble-updates noble-backports' \
    'Components: main restricted universe multiverse' \
    'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' \
    '' \
    'Types: deb' \
    'URIs: https://mirrors.aliyun.com/ubuntu/' \
    'Suites: noble-security' \
    'Components: main restricted universe multiverse' \
    'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' \
    > /etc/apt/sources.list.d/ubuntu.sources \
    && rm -f /etc/apt/sources.list
```

Debian still uses classic `sources.list`:
```
deb https://mirrors.aliyun.com/debian/ trixie main
deb https://mirrors.aliyun.com/debian-security/ trixie-security main
```

## pip / PyPI

```dockerfile
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_TRUSTED_HOST=mirrors.aliyun.com
RUN python3 -m pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ pillow fonttools
```

## What Aliyun does NOT mirror

- **vcpkg** GitHub repo → `https://mirrors.aliyun.com/github-release/microsoft/vcpkg/` returns 404.
  Keep vcpkg on GitHub with a shallow clone (`git clone --depth 1`); say so in a
  comment so nobody "fixes" it later.
- Rustup installer (`static.rust-lang.org`) — components come from Aliyun, the
  installer itself does not. (See workspace toolchain config for full rust/go
  mirror wiring.)

## Pitfalls

1. **Probe the component index, not just Release.** Release 200 + package in
   the wrong component = apt failure after you've already committed the config.
2. **deb822 vs sources.list** — writing the old format file on 24.04 does
   nothing; the `ubuntu.sources` file is authoritative (both can coexist, but
   only deb822 is read on 24.04+).
3. **`noble-security` must be a separate stanza** with the SAME base URI —
   security isn't a `-security` path segment on Aliyun; it's a separate suite
   line.
4. **`--no-install-recommends`** keeps the image lean and avoids pulling
   recommends from the wrong component.
5. **Document the mirror choice in the README** so a future agent doesn't
   "clean up" the mirror config back to upstream.

## Verification Checklist

- All suites probed 200, target package present in the right component index
- `groff`/`docker build`-able config; if no docker locally, state the gap
- README mentions mirror usage

## References

- Session example (2026-08-05): albdf dev container Dockerfile — Aliyun
  Ubuntu deb822 + PyPI wiring; verified noble suites 200, qt6-base-dev in
  universe, vcpkg unmirrored.
