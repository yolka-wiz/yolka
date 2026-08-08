# Case study: albdf build break — QFlags 32-bit overflow (Qt 6.8 vs 6.10)

Session 2026-08-06 (DB #30 fuzz-harness dispatch). The plan's exact build
command failed at HEAD; this is the diagnosis trail and the two valid fix
routes. Nothing here was "fixed" in that session — the harness task was
blocked and reported per contract.

## Symptom

```
qflags.h:54:33: error: static assertion failed: QFlags uses an int as storage,
so an enum with underlying long long will overflow.
... note: the comparison reduces to '(8 <= 4)'
ninja: build stopped: subcommand failed.
```

Fires from `Q_DECLARE_OPERATORS_FOR_FLAGS(pdftool::PDFToolAbstractApplication::Options)`
in `src/PdfTool/pdftoolabstractapplication.h:396`.

## Root cause (verified)

- `enum Option` in `src/PdfTool/pdftoolabstractapplication.h` gained
  `Rotate = 0x80000000, MovePage = 0x100000000, DeletePage = 0x200000000`
  in commit `4402b1c` "feat(cli): add rotate command" (2026-08-06).
- Qt 6.8's `QFlags` is 32-bit-storage-only (`static_assert(sizeof(Enum) <= sizeof(int))`).
  64-bit QFlags support arrived in Qt 6.9 (Qt docs: "Since Qt 6.9, QFlags
  supports 64-bit enumerations").
- The repo's `src/AGENT.md` says "Qt 6.10", but the machine had apt
  `qt6-base-dev 6.8.2` and `.github/workflows/ci.yml` pins `6.8.*` via
  install-qt-action → **both local and CI builds would fail at HEAD**.
- Vendored upstream base (`6bf5047`) enum stopped at `Redact = 0x02000000`;
  all 32-bit flags were already used by then, so the rotate commit overflowed.
- All parallel branches (`m10/core-redaction`, `m10/rtl-crossline-search`,
  `main`) carried the oversized values — not a worktree-local issue.

## Diagnosis commands that worked

```bash
grep -E "error:" build.log | sort -u          # single unique error
git log -S 'MovePage = 0x100000000' --oneline -- src/PdfTool/pdftoolabstractapplication.h
git show <base-sha>:src/PdfTool/pdftoolabstractapplication.h | grep -nE '= 0x[0-9A-Fa-f]{9}'
git merge-base --is-ancestor <sha> origin/main && echo on-main
for b in m10/* main; do git show "$b:src/PdfTool/pdftoolabstractapplication.h" | grep -cE '0x100000000|0x200000000'; done
```

Also worth checking: `find / -maxdepth 4 -name Qt6Config.cmake` to enumerate
available Qt installs, `qmake6 --version` for the system Qt, and
`stat -c '%y' <prebuilt-binary>` to prove a stale binary predates the break.

## Valid fix routes (pick per project rules)

1. **Renumber the flags** into the free 32-bit range — API change; requires
   orchestrator sign-off per AGENTS.md (public API shape). One logical commit.
2. **Build with Qt ≥ 6.9** — network available via pip mirror; works without
   touching repo code:
   ```bash
   pip install --user --break-system-packages aqtinstall
   aqt list-qt linux desktop                       # e.g. 6.10.3 available
   aqt install-qt linux desktop 6.10.3 linux_gcc_64 -O ~/qt
   cmake -S src -B src/build -G Ninja ... -DCMAKE_PREFIX_PATH=~/qt/6.10.3/gcc_64
   ```
   Note: `aqt list-qt ... --modules` showed NO qtsvg module for 6.10.3
   (svg may be folded into qtbase in 6.10) — verify `Qt6SvgConfig.cmake`
   exists in the install before relying on it.

## Outcome

Reported blocker with evidence; harness task (scripts/fuzz.sh, CI fuzz job,
docs) deferred until the build is green. Also flagged: CI `gate` job is red
at HEAD until the enum or the Qt pin is fixed.
