# yolka — clean memory baseline (no credentials, no host-specific secrets).
# Facts here are portable: they travel with the persona. Host-specific inventory
# belongs in the live profile's memory, NOT in this repo — secrets in a git repo
# burn on exposure. Rebuild this file from the live profile with build-identity.sh
# (which strips secrets) after significant environment changes.

SOCKS5 proxy at 127.0.0.1:10808 for web research (host xray/v2rayN).
§
User wants all infrastructure/architecture plans to include a self-critique section
reviewed through a cloud engineer's lens — call out SPOFs, bad architectural fits,
missing backups, version drift risks, bootstrapping problems, and complexity vs value.
Use a severity table format.
§
apt: socks5 proxy breaks apt; use mirror http://mirror.iranserver.com/ubuntu/
(99direct). pip: mirror2.chabokan.net/pypi/simple/ with proxy env unset.
§
Hermes agent — version pinned in VERSION file; version drift is the #1
reincarnation risk. Verify with `hermes --version` after install.
§
The identity lives in the yolka-wiz/yolka repo: SOUL.md, soul.json, memories,
skills, config. build-identity.sh refreshes; AGENT.md is the machine recipe;
README.md is the user guide. GitHub PAT deliberately redacted in repo.
§
Collaboration: research partner Rosetta runs in a separate container
(hermes-sandbox); /workspace is shared between yolka and Rosetta. Hand off via
inbox/ (to-rosetta-*.md) — she answers in inbox/from-rosetta-*.md.
