Iranian infra engineer; focus: OSS PDF editor albdf (yolka-wiz/al-bdf-engine) + viber proxy stack (amirrezaalavi/Viberayd+Viberoxy, viber-console). Background: package-mirror ecosystems (MiravaOrg) + network/infra.
§
Wants repos indexed for AI agents: REPO_MAP.md, .githooks/pre-commit regenerates+stages it, CONTRIBUTING.md (branch per task + commit each step; docs updated as you change; no push-to-main until ci/run-ci.sh green; no junk/secrets/data). Markdown docs except README must be STRUCTURED (H1+sections). WebUI wants: single main page, mobile-friendly, light/dark toggle, server <150MB RAM, few deps.
§
Prefers orchestrator-driven subagent development: yolka plans/orchestrates, subagents implement; verify subagent claims independently (commits, test output, pixel probes) before reporting success.
§
GitHub: provides fine-grained PATs + high-priv tokens for merge/release; expects agent to apply merges itself, temporarily relaxing branch-protection when stuck on review, then restore. Surface credential blockers explicitly; likes sequenced multi-step instructions with status checkpoints. name Yolka, company bornarad.co (NOT MiravaOrg), Iran; profile README yolka-wiz/yolka-wiz. Wants welcoming/friendly public text. Prefers lightweight, framework-native agent stacks.
§
Runs macOS VMs (Tahoe images) via tart for macOS/macOS-build testing.