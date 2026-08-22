# extfs-macos shared-checkout batch — what verification caught (2026-08-20)

A 3-agent parallel batch on ONE shared Rust workspace checkout (no worktrees),
scopes disjoint by file crate, then orchestrator re-verified the combined tree.
The verification — not the children's self-reports — surfaced four real defects,
three of them in the ORCHESTRATOR's own earlier code.

## 1. The orchestrator's green baseline was config-blind (GDT offset)
- Repo: a read-only ext4 parser (Rust). `groups.rs` hard-coded the group-
  descriptor-table byte offset as `2048`.
- All earlier passing tests used **default `mke2fs` images = 1 KiB block**
  (`first_data_block == 1` → GDT at `(1+1)*1024 = 2048`), so the constant
  passed every test while being wrong for larger block sizes.
- A parallel child (validation workstream) changed it to
  `(first_data_block + 1) * block_size`. Orchestrator's FIRST reaction: revert
  it as scope-creep / wrong. WRONG — the child was correct.
- Empirical proof that settled it (probe, not belief): build a real
  `mke2fs -b 4096` image, scan raw bytes. GDT fields (block_bitmap=5,
  inode_bitmap=21, inode_table=37) appear at byte **4096**, not 2048.
- Verified formula: ext4 GDT byte offset = `(first_data_block + 1) * block_size`
  → 2048 for 1 KiB (fdb=1), 4096 for `-b 4096` (fdb=0). Superblock is always at
  byte 1024; for block_size>1024 the superblock + GDT share block 0.
- **Lesson:** a green suite exercised only ONE configuration of the constant.
  Revert-on-instinct lost a correct fix; an artifact probe recovered it.

## 2. A workspace-wide change broke sibling tests (validation in `open()`)
- The child wired a bounds-audit (`validation.rs`) into `Filesystem::open`.
  Its own tests passed on 1 KiB images, but the audit wrongly rejected
  4 KiB images. The child's scope-isolated `-p <crate>` run never saw it; the
  orchestrator's full `cargo test --workspace` (differential suite) did.
- Takeaway: run the FULL integrated gate after all children, not per-crate.

## 3. SIGABRT in a panic-containment test = panic=abort defeating catch_unwind
- The C-ABI child's panic-containment test aborting with
  `thread caused non-unwinding panic. aborting.` (SIGABRT) is the classic
  signature of `panic = "abort"`.
- Root workspace set `[profile.release] panic = "abort"` (correct for CLI
  binaries) — but under `panic=abort`, `std::panic::catch_unwind` CANNOT
  contain a panic; it aborts the whole hosting process.
- For a Rust FFI library (`cdylib`/`staticlib` bound into a Swift/C host),
  the panic-containment guarantee ONLY holds when built `panic = "unwind"`.
  Cargo profiles are workspace-global (no per-package panic), so the shippable
  FFI artifact must be built with `RUSTFLAGS="-C panic=unwind"` (or a build
  script / separate profile). Document this next to the FFI entry points and
  in the C header; verify the shipped artifact's panic strategy.
- Debugging path: read the live transcript's `panicked at:` line (the abort
  summary hides the real panic site); `RUST_BACKTRACE=1 cargo test -p <crate>`.

## 4. Differential false-positive: mke2fs `lost+found`
- `mke2fs` auto-creates a root `lost+found` dir that a host staging manifest
  (populated test content) doesn't contain → image-only row in the diffs.
- Fix: drop `lost+found` on the image side of the comparison (both in the Rust
  integration test and the shell `compare` projection). Housekeeping, not
  content under test.

## 5. Path-resolution bug caught by re-running the gate
- `lookup_path` resolved a RELATIVE symlink target against root instead of the
  directory containing the link → `/dir/link -> sub/file.txt` were ENOENT.
  POSIX-correct fix: relative symlink targets resolve against the link's parent
  directory; absolute restarts from root; bound the follow-depth to detect
  loops. The test was later reconciled (reads of a resolved path return the
  resolved file; the RAW target needs the unfollowed inode).

## Coordination notes for one-checkout parallel batches
- Keep scopes disjoint by FILE (one agent per crate/module).
- Tell each child: run `cargo test -p <its crate>`, NOT `cargo test
  --workspace` (compiles siblings' half-written code and makes IT look at
  fault); and do NOT `git add -A && git commit` (sweeps siblings' uncommitted
  files) — commit only `git add <its own files>`.
- Orchestrator commits the verified combined state itself, in logical units.

## Batch 2/3 refinements (2026-08-20, later batches, same extfs repo)
- **Stricter "stage, don't commit" review mode.** When the user says "have
  subagents implement; test their results and give feedback," instruct each
  child to make its edits but NOT commit at all (leave files un-staged or
  staged, not committed) so the orchestrator can review the WHOLE batch before
  anything hardens into history. This lets the orchestrator revert a single
  wrong subagent change cleanly, then commit ONE coherent per-batch commit
  with an accurate message (and, critically, prevents a child's `git add -A`
  from sweeping a sibling's or another batch's uncommitted files into its own
  commit). Children were told "do not commit" across the whole session; HEAD
  stayed pinned at the last verified commit until the orchestrator committed.
- **Mac-only scaffold portability, proven on Linux.** A workstream that writes
  an Apple FSKit/Swift adapter CANNOT compile Swift here — but its Rust half is
  still CI-provable on Linux: `rustup target add aarch64-apple-darwin` then
  `cargo build -p <pure-stdlib core> --target aarch64-apple-darwin` (builds,
  no Apple SDK needed) and `cargo check -p <capi> --target aarch64-apple-darwin`
  (type-checks; the cdylib/staticlib LINK still needs the Apple SDK). Verified
  rc=0 for both. The macOS CI job then GATES on the Rust core build/test +
  cross-compile, and makes the unsigned `xcodebuild` of the Swift NON-gating
  (continue-on-error) with `RUSTFLAGS="-C panic=unwind"` for the linked
  staticlib. Swift behavior stays `UNVERIFIED` and is held for the real Mac/VM
  (tart/Tahoe). Check the Swift marshals to the real C-ABI symbols statically
  (grep exported `extfs_*` names vs the header) since you cannot run it.
- **Fuzz smoke vs nightly via env-var parameterization.** Parameterize the
  fuzz test's iteration budget with an env var (e.g. `EXTFS_FUZZ_ITERATIONS`,
  default 400) and a FIXED seed, so a PR smoke and a nightly long-run share ONE
  deterministic entrypoint (`scripts/run-fuzz-smoke.sh` honors it; nightly sets
  a large budget and also runs the differential). Keeps PR CI fast while
  allowing an unbounded nightly without forking the harness.
- **Verify the orchestrator's own earlier table is not stale.** The session
  opened with the orchestrator claiming "3/3 differential passed"; re-running
  cleanly after later changes exposed that the latent symlink bug (Section 5)
  had been there all along and the earlier pass was stale/misattributed. Re-run
  the gate genuinely (clean binary) before trusting an old "passed" you
  recorded yourself — the same rule that applies to children's claims applies
  to your own past claims.
