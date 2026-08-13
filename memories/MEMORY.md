SOCKS5 socks5://192.168.4.120:10909 for geo-blocked CDNs; prefer direct egress.
§
User wants all infrastructure/architecture plans to include a self-critique section
reviewed through a cloud engineer's lens — call out SPOFs, bad architectural fits,
missing backups, version drift risks, bootstrapping problems, and complexity vs value.
Use a severity table format.
§
Caveats: goproxy no sumdb (GOSUMDB=off); rustup mirror lacks installer (use static.rust-lang.org).
§
Hermes version pinned in VERSION file — version drift is #1 reincarnation risk; verify with `hermes --version` after install.
§
Identity lives in yolka-wiz/yolka repo: SOUL.md, soul.json, memories, skills, config; build-identity.sh refreshes.
§
Rosetta = Hermes profile beside yolka (~/.hermes/profiles/rosetta, research agent, deepseek-v4-flash/opencode-go); backup in private yolka-wiz/rosetta.
§
Dev identity: git user.name=yolka, user.email=yolka@bornarad.co. GitHub: SSH key id_ed25519_github + gh CLI authed (PAT in ~/.config/gh/hosts.yml).
§
Container limits: ICMP blocked (no cap_net_raw) — use TCP. LAN 192.168.4.4 via gw 10.77.0.1.
§
web_search uses ddgs backend; web_extract needs keyed backend (none) — curl raw URLs as fallback.
§
Vision: GUI editor. PDF4QT v1.6.0.0 vendored src/ behind ALBDF_BUILD_GUI=ON; TTS out. vcpkg /home/agent/vcpkg-cache/vcpkg; main protected (PR+1, owner bypass).
§
Upstream PDF4QT = JakubMelka/PDF4QT (MIT, no CLA, no PR CI). al-bdf-engine has NO git ancestry (vendored at M1) — sync = file-level re-vendor, never git pull.
§
Upstream PR vehicle: yolka-wiz/pdf4qt-rtl (MIT fork of PDF4QT, separate from GPL albdf). RTL engine keeps harfbuzz+fribidi (Qt-native lacks cluster/bidi APIs).
§
opencode endpoint opencode.ai/zen/go/v1: model deepseek-v4-flash (NOT ds-v4-flash); rejects 'developer' role. Agno LO agents playground (skill agno-agent-playground); results → yolka-wiz/libreoffice-agent-results. User=<REDACTED> (2CPU/<2GB embeds), benchmark before choosing, stop rabbit-holes.
§
LO bug-cluster: playground/cluster conductor (cron 30m; lo-writer → yolka-wiz/libreoffice-work, fork of upstream; history cluster_history.db). LO unshallow fails — use --depth=200.