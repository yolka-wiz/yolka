SOCKS5 socks5://192.168.4.120:10909 for geo-blocked CDNs; prefer direct egress.
§
User wants all infrastructure/architecture plans to include a self-critique section
reviewed through a cloud engineer's lens — call out SPOFs, bad architectural fits,
missing backups, version drift risks, bootstrapping problems, and complexity vs value.
Use a severity table format.
§
Caveats: goproxy no sumdb (GOSUMDB=off); rustup mirror lacks installer (use static.rust-lang.org).
§
Hermes version pinned in VERSION file — drift = #1 reincarnation risk; verify `hermes --version` after install.
§
Identity lives in yolka-wiz/yolka repo: SOUL.md, soul.json, memories, skills, config; build-identity.sh refreshes.
§
Rosetta: Hermes profile beside yolka; backup in private yolka-wiz/rosetta.
§
Dev identity: git yolka/yolka@bornarad.co; GitHub SSH id_ed25519_github + gh CLI authed (PAT ~/.config/gh/hosts.yml).
§
Container limits: ICMP blocked (no cap_net_raw) — use TCP. LAN 192.168.4.4 via gw 10.77.0.1.
§
Vision: GUI editor. PDF4QT v1.6.0.0 vendored src/ behind ALBDF_BUILD_GUI=ON; TTS out. vcpkg /home/agent/vcpkg-cache/vcpkg; main protected (PR+1, owner bypass).
§
Upstream PDF4QT = JakubMelka/PDF4QT (MIT, no CLA, no PR CI). al-bdf-engine has NO git ancestry (vendored at M1) — sync = file-level re-vendor, never git pull.
§
Upstream PR vehicle: yolka-wiz/pdf4qt-rtl (MIT fork of PDF4QT, separate from GPL albdf). RTL engine keeps harfbuzz+fribidi (Qt-native lacks cluster/bidi APIs).
§
opencode: model deepseek-v4-flash.
§
LO cluster: conductor cron 30m in playground/; lo-writer → yolka-wiz/libreoffice-work; unshallow fails — use --depth=200.
§
Viber stack: Viberayd+Viberoxy (upstream amirrezaalavi/*, forks yolka-wiz/*, fork→PR) + viber-console = Go bundler/WebUI (supervised children, env-file config, vanilla SPA, zero-dep). Prefs: supervisor>systemd, verify merged PRs compile, daemons tolerate bad input.
§
extfs-macos driver: github.com/yolka-wiz/extfs-macos (public, main); clone /home/agent/workspace/extfs-macos. Core CI-green; Swift FSKit scaffold UNVERIFIED (tart Mac). mkfs blocked in shell — fixtures via cargo tests. extfs-capi build needs panic=unwind (workspace release=abort).