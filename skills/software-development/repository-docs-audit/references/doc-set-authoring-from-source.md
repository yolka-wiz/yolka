# Authoring an accurate doc set from source — worked pattern

Session: wrote the full doc set (architecture, supported-features,
security-model, testing, macos-setup, REPO_MAP) for `extfs-macos`, a read-only
Rust ext2/3/4 filesystem. The reusable discipline, concrete.

## Sequence that worked

1. **Locate + orient.** Given `/workspace/extfs-macos` which didn't exist:
   `find / -maxdepth 4 -name extfs-macos -type d` → real path
   `/home/agent/workspace/extfs-macos`. Then `git log --oneline -5` and
   `git ls-files` to enumerate the *committed* tree.
2. **Read the authoritative sources per fact area**, then write:
   - Features whitelist → quote `features.rs SUPPORTED_INCOMPAT` and the
     rejection rules verbatim (bigalloc/MMP/encrypt/inline_data/journal_dev).
   - Error model → `error.rs` enum variants (list them all).
   - Read path / Filesystem / Block trait → `read_only.rs`, `block.rs`.
   - Dirty gate → `superblock.rs check_clean` (EXT2_VALID_FS + RECOVER → NotExt).
   - Fuzz no-panic (400 deterministic mutations) → `tests/fuzz.rs`.
   - Differential pipeline + tools (mke2fs/debugfs/e2fsck) + content-truth
     projection → the `scripts/*.sh` + `extfs-testkit/tests/manifest_diff.rs`.
   - FUSE EROFS/mount RO → `adapters/linux-fuse/src/main.rs`.
3. **Audit the README vs the tree.** README's layout block claimed
   `adapters/macos-fskit/`, `tests/`, `fuzz/`. Reality: `macos-fskit/` did NOT
   exist; `tests/`/`fuzz/` were empty placeholders (fixtures generated on
   demand, not committed). `ls -d` every listed dir; surface the gap.
4. **Call out skeleton bounds honestly.** `extfs-capi/` was types-only:
   `#[repr(C)]` `ExtfsHandle/Stat/Dirent/ErrorCode` but NO `#[no_mangle]`
   trampolines (verified by grepping for `no_mangle` across the tree → 0 hits
   besides comments). Docs say "types-only today", not "C ABI done".
5. **Flag cross-doc tension instead of papering over it.** Release profile set
   `panic="abort"` while the security model relies on `catch_unwind` — noted as
   a real consideration, not hidden.
6. **macOS = UNVERIFIED, not "planned and fine".** No adapter, no macOS CI.
   `macos-setup.md` opens with a STATUS banner, lists prereqs (real Mac / tart/
   Tahoe self-hosted runner, macOS 15.4+, `com.apple.developer.fskit.fsmodule`
   entitlement), a build-stock-Apple-sample-first checklist, and open questions.
7. **Verify deliverable** — `ls -la docs/ REPO_MAP.md` + `head -1` each file to
   confirm H1 headings, then report every file written + the sources read.

## Why it matters

Repo documentation is only useful if "feature/tool X is supported" traces to
code, not to an aspirational README. A doc set that faithfully distinguishes
implemented / planned / placeholder is ground truth for later agents; one that
paraphrases the README propagates its drift. The skill-level lesson: for any
doc-authoring task, go straight to source identifiers and the committed tree,
and mark anything unvalidated as such.
