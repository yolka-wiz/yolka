# Declaring a release — end-to-end recipe (albdf 0.2.0 case)

Use when the user says "update docs, db and declare a release" / "bump version
and release". The recipe is the ordered list of steps; each one has a verify
step before moving on. Do NOT skip the gate or the determinism check — both
caught real breakage in the 0.2.0 run.

## Order of operations (verified 2026-08-07)

1. **Version bump — grep for the old version FIRST.**
   - Bump `set(ALBDF_VERSION X.Y.Z)` in `src/CMakeLists.txt`.
   - `grep -rn "OLDVER" src/ scripts/ ci/` before building — a test/script
     almost always hardcodes the version string (albdf's `src/tests/smoke.sh`
     grepped `albdf (0\.1\.0|1\.6\.0\.0)` and failed with
     `FAIL version string (got: albdf 0.2.0)`).
   - Make the check FUTURE-PROOF so the next bump doesn't break it again:
     `grep -qE "albdf (0\.[0-9]+\.[0-9]+|1\.6\.0\.0)"` — accept any 0.x.y.
   - Rebuild + `ctest` before anything else: the version string is exercised
     by smoke/CLI tests that don't fail until you run the full suite.
2. **Update docs.** `docs/RELEASES.md` gets a new top section (project name →
     version → date → branch → what's new per milestone → quality gates →
     known limitations). `plans/PLAN.md` milestone checkboxes go `[ ]`→`[x]`.
3. **Update the DB.** `scripts/db.py task-add ...` for the release item, then
   `task-done <id> --ref <release-commit-sha>` after the release commit lands.
   The DB is gitignored — updates live only in the working checkout.
4. **Commit the release changes** (version + smoke + RELEASES.md + PLAN.md +
   regenerated REPO_MAP.md) as ONE commit: `release: <name> X.Y.Z — ...`.
   Regenerate REPO_MAP (`python3 scripts/gen-repo-map.py`) before staging.
5. **Run the FULL gate on the release commit** (`bash ci/run-ci.sh` with the
   machine's real VCPKG_ROOT) — Release+ctest, ASAN+ctest, format. A release
   tagged from an un-gated commit is how broken tags happen. 14/14 + ASAN
   14/14 + format OK for albdf 0.2.0.
6. **Build the deterministic artifact and PROVE determinism.**
   - `bash scripts/package.sh --build-dir src/build --out-dir dist --version X.Y.Z`
   - Build it a SECOND time into a different out-dir and compare sha256 —
     identical bytes across runs is the reproducible-build guarantee
     (0.2.0: `905d5510...` twice). If the hashes differ, STOP — find the
     nondeterminism (mtimes, SOURCE_DATE_EPOCH, timestamps) before releasing.
7. **Tag + push.** `git push origin main` first, then
   `git tag -a X.Y.Z -m "..."` and `git push origin X.Y.Z`. The tag must
   point at the gated release commit. Verify: `git ls-remote --tags origin`.
8. **Create the GitHub Release object** — the ONLY step needing the token,
   and it fails differently from everything else (see below).

## The token trap: `gh release create` needs Contents:write, not "admin"

- `gh release create X.Y.Z dist/*.tar.gz dist/*.sha256 --title ... --notes ...`
  returns `HTTP 403: Resource not accessible by personal access token` when
  the fine-grained PAT lacks **Contents: Read and write** — even if the user
  calls the token "the admin key". "Admin" in a fine-grained PAT is just a
  name; the permission matrix is what matters.
- PR creation works with Pull-requests: R/W only; releases additionally need
  Contents: R/W. The push/tag needs NO token (SSH/HTTPS git auth).
- **Probe the scope before trusting the label**: a quick
  `curl -X PUT .../contents/__probe__ -d '...'` returning 403 tells you
  Contents is read-only; `gh api .../releases` returning 200 (read) does NOT
  prove write.
- Fix: user edits the existing fine-grained PAT at
  `https://github.com/settings/tokens?type=beta` (Contents → Read and write);
  the stored token string keeps working, no re-paste. Then retry the exact
  command.
- UI fallback that always works: **Releases → Draft a new release → pick the
  pushed tag** → attach the tarball + .sha256 → paste notes. Give the user
  the exact notes markdown.

## The fork trap: `gh release create` targets the WRONG repo

In a fork with an `upstream` remote added (recon adds it for diffing), `gh`
resolves the default repo from the remote config — and it may pick UPSTREAM.
Symptom (albdf 0.3.0, 2026-08-07): the tag was pushed to `origin` but
`gh release create 0.3.0 ...` failed with:

```
tag 0.3.0 exists locally but has not been pushed to JakubMelka/PDF4QT,
please push it before continuing or specify the `--target` flag
```

The fix is NOT pushing to upstream — it's pinning the repo:
`gh release create ... --repo yolka-wiz/al-bdf-engine` (or set it once with
`gh repo set-default`). Always pass `--repo <owner>/<repo>` explicitly for
release/pull operations in a fork; never rely on gh's remote-derived default.
This bites anywhere `gh` shells out (release create, `gh run view`, PR
creation) — `--repo` is the universal pin.

## Version-drift self-check (release checklist)

Version lives in FOUR places that can disagree: CMakeLists.txt, the git tag,
docs/RELEASES.md, and the DB task. Before declaring done, assert:
- binary `--version` == CMake version == tag == RELEASES.md heading.
- `git describe --tags` matches the CMake version (a stale tag pointing at an
  old commit is the drift that bites later).
