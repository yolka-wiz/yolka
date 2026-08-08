# albdf release workflow — verified on 0.2.0 (2026-08-07)

Reproducible recipe for shipping an albdf release. Every step was executed for
0.2.0 (the first public release after the pdfedit→albdf rename).

## Prereqs

- Branch protection active on `main` (ruleset: PR + 1 approval; owner has an
  admin bypass so direct pushes work for the owner/agent with owner creds).
- Fine-grained PAT with **Contents: read and write** (needed for
  `gh release create`; read-only Contents → 403 even though git push works —
  see the PAT gotcha at the end).

## Steps

1. **Version bump** in `src/CMakeLists.txt`:
   `set(ALBDF_VERSION 0.2.0)` (was `0.1.0`).
   **Trap:** the FIRST ctest failure after a bump is a test/script that
   hardcodes the old version — `src/tests/smoke.sh` grepped
   `albdf (0\.1\.0|1\.6\.0\.0)`. Before bumping: `grep -rn "0\.1\.0" src/tests/ scripts/`.
   Fix future-proof: `grep -qE "albdf (0\.[0-9]+\.[0-9]+|1\.6\.0\.0)"` so the next
   bump doesn't break it again.

2. **Docs:** add the release section to `docs/RELEASES.md` (top of file; keep
   the historical 0.1.0 pdfedit notes below, marked as pre-rename). Tick the
   M11/release boxes in `plans/PLAN.md`. Regenerate `REPO_MAP.md`
   (`python3 scripts/gen-repo-map.py`).

3. **Gate must be ALL GREEN before tagging** — release commit is the tag
   target, so it must be fully verified:
   `export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg && bash ci/run-ci.sh`
   (background + notify; ASAN stage 15-40 min). Expect: Release ctest 14/14,
   ASAN 14/14, `clang-format gate OK (N files)`, `CI: ALL GREEN`.

4. **Commit + push main** (`git push origin main`), then **build the
   deterministic tarball**:
   `bash scripts/package.sh --build-dir src/build --out-dir dist --version 0.2.0`
   → `dist/albdf-0.2.0-linux-x86_64.tar.gz` + `.sha256`.
   **Prove determinism:** run package.sh a SECOND time into a different out-dir
   and compare sha256 — must be identical
   (`sha256sum dist/... /tmp/pkg2/...`). If they differ, the build isn't
   reproducible; do NOT release.

5. **Tag + push:**
   `git tag -a 0.2.0 -m "albdf 0.2.0 — ..." && git push origin 0.2.0`
   (annotated tag; point it at the gated release commit).

6. **Create the GitHub release** (needs Contents:write):
   `gh release create 0.2.0 dist/albdf-0.2.0-linux-x86_64.tar.gz dist/albdf-0.2.0-linux-x86_64.tar.gz.sha256 --title "..." --notes "..."`
   **`--repo` gotcha (hit on 0.3.0):** when the local repo has an `upstream`
   remote configured (we added `JakubMelka/PDF4QT` for vendoring), `gh release
   create` may try to publish to UPSTREAM and fail with
   `tag 0.3.0 exists locally but has not been pushed to JakubMelka/PDF4QT`.
   Always pass `--repo yolka-wiz/al-bdf-engine` explicitly. The same applies to
   PR creation via `gh` (fine-grained PATs also fail PR create via GraphQL but
   succeed via the REST endpoint — `curl -X POST .../pulls` with a
   `-d '{"head":..., "base":...}'` payload works when `gh pr create` 403s).
   Since 0.3.0 the release also carries the **AppImage** asset
   (`dist/albdf-0.3.0-x86_64.AppImage` + its `.sha256`) built by
   `packaging/build-appimage.sh` — attach all three artifact pairs (tarball,
   AppImage, and their sidecars) and verify each downloaded sha256 matches
   local (see step 7).

7. **Verify the release object independently** — don't trust the create
   response: list releases via API, confirm both assets attached, then
   re-download the tarball from the release URL and `sha256sum` it against the
   local build. Same hash = published artifact is the verified artifact.

8. **DB:** add + close a release task with `task-done --ref 0.2.0`.

## Fine-grained PAT gotcha (hit 2026-08-07)

`gh release create` → `HTTP 403: Resource not accessible by personal access
token` even when the same token (or another one) pushes git fine. Fine-grained
PATs gate Releases behind **Contents: read and write**; read-only Contents, or
a token *named* "admin" with no such permission, fails. Confirm with a write
probe (201 = can write, 403 = scope missing):
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X PUT \
  -H "Authorization: Bearer $(gh auth token)" \
  "https://api.github.com/repos/<owner>/<repo>/contents/__perm_probe__.txt" \
  -d '{"message":"perm probe","content":"cGVybQ=="}'   # then DELETE the probe
```
Fix: user edits the token at https://github.com/settings/tokens?type=beta →
Repository permissions → Contents → Read and write → Save. The existing token
value in `~/.config/gh/hosts.yml` picks up the scope immediately — no re-auth.

## Post-release housekeeping (0.2.0 did all of these)

- Delete stale remote branches (`git push origin --delete <branch>`): the
  pre-rewrite `feature/wave1-*` and the merged `m10/*` branches.
- Remove merged worktrees (`git worktree remove --force <wt>` then prune).
- Clean `/tmp` build artifacts (qt-*, icu, bench-*).
