# Aliyun Mirror Layout (mirrors.aliyun.com)

Verified 2026-08-05 from a Debian 13 (trixie) x86_64 container with direct egress.
Probe method that worked: `curl -s -o /dev/null -w '%{http_code}' -m 10 <GET url>` — deep paths,
not roots, not HEAD.

## Surface matrix

| Surface | URL | Notes |
|---|---|---|
| apt (Debian) | `https://mirrors.aliyun.com/debian` | `dists/trixie/Release` → 200 |
| apt security | `https://mirrors.aliyun.com/debian-security` | `dists/trixie-security/Release` → 200 |
| PyPI | `https://mirrors.aliyun.com/pypi/simple/` | `simple/uv/` → 200 |
| Go modules | `https://mirrors.aliyun.com/goproxy` | module `@v/list` → 200 for common paths; **NO sumdb tiles** |
| Go tarballs | `https://mirrors.aliyun.com/golang/` | e.g. `go1.26.5.linux-amd64.tar.gz` — same sha256 as go.dev |
| rustup dist | `https://mirrors.aliyun.com/rustup` | `dist/channel-rust-stable.toml` → 200 |
| rustup update root | `https://mirrors.aliyun.com/rustup/rustup` | `release-stable.toml` → 200 |
| crates.io sparse index | `https://mirrors.aliyun.com/crates.io-index/` | `config.json` → 200 |
| Ubuntu | `https://mirrors.aliyun.com/ubuntu` | exists (host was Debian; unused) |

## NOT on Aliyun (probe before assuming)

- **`rustup-init` installer binary** — `.../rustup/dist/x86_64-unknown-linux-gnu/rustup-init` → 404.
  Fetch from `https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init` (~20 MB),
  then run it with the env vars below so all toolchain components still come from Aliyun.
- **Go sumdb tiles** — `.../goproxy/sumdb/sum.golang.org/...` → 404. Fix: `go env -w GOSUMDB=off`.

## Config snippets

apt `/etc/apt/sources.list` (backup first: `sudo cp ... .bak-$(date +%Y%m%d)`):
```
deb https://mirrors.aliyun.com/debian trixie main contrib
deb https://mirrors.aliyun.com/debian trixie-updates main contrib
deb https://mirrors.aliyun.com/debian-security trixie-security main contrib
```

`~/.config/pip/pip.conf`:
```
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
```

`~/.config/uv/uv.toml`:
```
index-url = "https://mirrors.aliyun.com/pypi/simple/"
```

`~/.cargo/config.toml`:
```
[source.crates-io]
replace-with = "aliyun"

[source.aliyun]
registry = "sparse+https://mirrors.aliyun.com/crates.io-index/"
```

Go (persists via `go env -w`, no sudo, no bashrc needed):
```
go env -w GOPROXY="https://mirrors.aliyun.com/goproxy,direct"
go env -w GOSUMDB=off
```

Rust (env vars — must be exported BEFORE rustup runs; add to `~/.bashrc`):
```
export RUSTUP_DIST_SERVER="https://mirrors.aliyun.com/rustup"
export RUSTUP_UPDATE_ROOT="https://mirrors.aliyun.com/rustup/rustup"
```

## End-to-end proofs (real output, 2026-08-05)

- **Go**: `go get github.com/google/uuid@latest` → `go: downloading github.com/google/uuid v1.6.0`,
  module cache populated. (First attempt failed on sumdb 404 until `GOSUMDB=off`.)
- **Cargo**: `cargo new` + `cargo add serde` + `cargo build` → "Hello, world!",
  fetch lines show `Downloaded ... (registry \`aliyun\`)`.
- **uv**: `uv pip install rich` → rich 15.0.0 installed via Aliyun index.
- **apt**: `apt update` clean after switching sources.
- **Go tarball via Aliyun**: `mirrors.aliyun.com/golang/go1.26.5.linux-amd64.tar.gz` (66,879,095
  bytes) sha256-matched the go.dev JSON checksum, while `dl.google.com` 404'd the same file.

## Relevant quirk

`go.dev/dl/?mode=json` returns 405 to HEAD and 200 to GET; crates.io API returns 403 to HEAD;
PyPI index returns 405 to HEAD. None of these indicate blockage — always retest with GET before
declaring an endpoint unreachable.
