# cargo-audit reference

cargo-audit installs + operational details for auditing a Rust workspace's
Cargo.lock against the RustSec advisory-db (https://rustsec.org/advisories).

## Install
```bash
export PATH="$HOME/.cargo/bin:$PATH"
cargo install cargo-audit --locked     # compiles ~2min release; verify with `cargo audit --version`
```
No special rustsec path needed unless the install/network is broken; the plain
`cargo install` path is the normal, working one.

## Run
```bash
cargo audit                 # human-readable; exit 0 = clean, non-zero = findings (default denies vulns)
cargo audit --json          # machine-readable; parse for structured confirmation
```
`exit 0` is NOT proof of a clean tree by itself — a successful run with an
informational/unsound "warning" (e.g. RUSTSEC-2021-0154, `informational = "unsound"`)
still exits 0 by default. To confirm truly clean, use JSON:
```bash
cargo audit --json 2>/dev/null | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d['vulnerabilities']['list']); print(d['warnings']['list'])"
```
Reports findings verbatim in the human output: `Crate`, `Version`, `Warning`
(vulnerabilities / unmaintained / yanked / unsound), `Title`, `ID`, `URL`.

## Advisory DB and finding patched versions
Cached locally at `~/.cargo/advisory-db/crates/<crate>/<RUSTSEC-id>.md`. To decide
if a safe bump clears a finding, read the advisory TOML frontmatter:
```toml
informational = "unsound"        # if present: does NOT gate (exit 0)
[versions]
patched = [">= 0.16.0"]          # the version that fixes it
[affected.functions]
"crate::Session::new" = [">= 0.5.0"]
```
- `informational = "unsound"` / `"unmaintained"`: exit 0, advisory-only. Safe to
  bump if trivial, but not a gate failure — don't force a build break over it.
- Real `[advisory]` (vulnerabilities) make `cargo audit` exit non-zero.

## Bumping a dependency safely
1. Read the advisory `[versions].patched` for the target version.
2. Bump in the crate that declares it (e.g. `adapters/<x>/Cargo.toml`,
   `fuser = { version = "0.15", ... }` -> `"0.16"`).
3. `cargo update -p <crate>` to lock, then `cargo build --workspace` to verify
   the API still compiles before considering it done.
4. Re-run `cargo audit` to confirm the advisory is gone.
Only persist the bump if the build stays green; otherwise document instead of
forcing a break.

## Aliyun-mirror 403 yank-check noise (environment-specific)
With a cargo registry mirrored to Aliyun, `cargo audit` prints many lines of
```
error: couldn't check if the package is yanked: registry: status code '403 Forbidden'
```
on **stderr**. These are non-fatal (exit code unaffected, findings still printed)
and do NOT occur on GitHub Actions' crates.io. Treat them as noise: confirm the
real verdict with `--json`, and don't choke the CI step on stderr. Do not add a
`|| echo skip` to silence them — that would un-gate the step.
