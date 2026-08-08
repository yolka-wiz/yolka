SOCKS5 socks5://192.168.4.120:10909 for geo-blocked CDNs; prefer direct egress.
§
User wants all infrastructure/architecture plans to include a self-critique section
reviewed through a cloud engineer's lens — call out SPOFs, bad architectural fits,
missing backups, version drift risks, bootstrapping problems, and complexity vs value.
Use a severity table format.
§
Mirrors: user prefers https://mirrors.aliyun.com/ — apt debian+debian-security, PyPI (pip.conf + uv.toml), goproxy (GOPROXY env), rustup dist (RUSTUP_DIST_SERVER), crates.io sparse index (~/.cargo/config.toml). Caveats: aliyun goproxy lacks sumdb tiles (GOSUMDB=off); aliyun rustup mirror lacks rustup-init installer (fetch from static.rust-lang.org).
§
Hermes version pinned in VERSION file — version drift is #1 reincarnation risk; verify with `hermes --version` after install.
§
Identity lives in yolka-wiz/yolka repo: SOUL.md, soul.json, memories, skills, config; build-identity.sh refreshes. GitHub PAT deliberately redacted.
§
Research partner Rosetta runs in a separate container; /workspace shared. Hand off via inbox/ (to-rosetta-*.md → from-rosetta-*.md).
§
Dev identity: git user.name=yolka, user.email=yolka@bornarad.co. GitHub: SSH key id_ed25519_github + gh CLI authed (PAT in ~/.config/gh/hosts.yml).
§
Container limits: ICMP blocked (no cap_net_raw) — use TCP. LAN 192.168.4.4 via gw 10.77.0.1.
§
web_search uses ddgs backend; web_extract needs keyed backend (none) — curl raw URLs as fallback.
§
Vision: full GUI editor. GUI RESTORED (M12): PDF4QT v1.6.0.0 vendored into src/ behind ALBDF_BUILD_GUI=ON; TTS compile-out (fork divergence); AppImage via packaging/build-appimage.sh (needs APPIMAGE_EXTRACT_AND_RUN=1 + qt6-svg-plugins + file). M13: GUI RTL search wired; R#4/S#3 fixed. Release 0.3.0 + AppImage live. vcpkg /home/agent/vcpkg-cache/vcpkg; main protected (PR+1, owner bypass).
§
Upstream PDF4QT = JakubMelka/PDF4QT: MIT (relicensed 2025-04-27), no CLA, CI not run on PRs; al-bdf-engine ~1.4k commits behind upstream.