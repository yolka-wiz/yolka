# Proving a Rust C ABI for Apple/Swift from Linux + bridging to it

Worked on the extfs project: a panic-safe Rust C ABI (`extfs-capi`, crate-type
`["cdylib","staticlib","rlib"]`) that a Swift/FSKit macOS adapter calls. No
macOS/Swift/Xcode exists in the Linux dev environment, so the *verifiable* part
is the Rust cross-compile; the Swift layer is written correct-by-construction
and left UNVERIFIED. Commit lineage: `02d6955` (two entries below).

## 1. Cross-compile proof for aarch64-apple-darwin (all done on Linux)

```bash
export PATH="$HOME/.cargo/bin:$PATH"
rustup target add aarch64-apple-darwin
```

| Command | Result | Why |
|---|---|---|
| `cargo build -p extfs-core --target aarch64-apple-darwin` | ✅ succeeds | Pure-`std` core needs no Apple SDK |
| `cargo check -p extfs-capi --target aarch64-apple-darwin` | ✅ succeeds | Type-checks/compiles the FFI crate, no link |
| `cargo build -p extfs-capi --target aarch64-apple-darwin` | ❌ **link** fails | Needs the Apple SDK/linker |

The capi link failure is environment-driven, not a code bug:
```
error: linking with `cc` failed ... cc: error: unrecognized command-line option '-arch'
       cc: error: unrecognized command-line option '-mmacosx-version-min=11.0.0'
```
The Linux `cc` can't parse Apple linker flags. Compilation reached codegen
fine; only the `cdylib`/`staticlib` *link* step needs `xcrun`/`DEVELOPER_DIR`/
`SDKROOT`, i.e. a real Mac (or macOS VM / macos-* runner).

Report this honestly as "compile verified, link-limited" — do NOT claim the
Apple binary was produced on Linux.

## 2. Swift/FSKit scaffold writing rules (no Swift toolchain present)

When the deliverable's Swift can't be compiled in this environment, keep it a
well-formed scaffold and say so plainly. Techniques that keep it
correct-by-construction (all used in `adapters/macos-fskit/`):

- **Import the shared C header by crate-relative path**, two interchangeable
  mechanisms (use one, not both):
  - *Bridging header* (`ExtfsBridging.h`): `#include <extfs.h>` + build setting
    `HEADER_SEARCH_PATHS = $(SRCROOT)/../../crates/extfs-capi/include`. The LSP
    in a Linux container will flag the `#include` as not found — that is expected
    and non-blocking; the path resolves only at Xcode build time.
  - *`module.modulemap`*: `module ExtfsC { header "../../../../crates/.../extfs.h" export * }`
    with `SWIFT_INCLUDE_PATHS` pointing at the module-map dir (resolves relative
    to the map's own directory, no search path needed).
- **Mirror the block_ops vtable in Swift**: a backend class holding the byte
  source; three top-level `@convention(c)` funcs recover the backend from the
  opaque `ctx` via `Unmanaged<Backend>.fromOpaque(ctx).takeUnretainedValue()`;
  `makeCOps()` builds the C struct with `Unmanaged.passUnretained(self).toOpaque()`
  as `ctx`. Keep the source alive for the handle's lifetime (the C ABI's
  caller-owned-ctx rule). Pure Swift, no foreign parsing.
- **Contain the unverified surface with tags**: any Swift call whose exact
  importer-generated label / optionality (Swift C importer mangles C symbols, e.g.
  `extfs_lookup(handle,parent,name,nameLen,ino)` labels and whether `void*`
  params import as optional) or FSKit-proprietary API is uncertain should be
  tagged `TODO(swift-cabi)` / `TODO(FSKit)` rather than invented. Stub
  unverifiable FSKit operations to behave safely (e.g. an unimplemented block
  read throws `EIO` so the core never sees garbage).
- **Never claim it works.** Stage the files, don't commit an unvalidated Swift
  layer into verified history; the git log must not mix scaffold into verified
  commits. Document a per-item verified/unverified matrix in the adapter README.
- Keep signing OFF (`CODE_SIGNING_ALLOWED=NO`) in any CI that attempts an
  xcodebuild; FSKit *activation* additionally needs the
  `com.apple.developer.fskit.fsmodule` entitlement + a signed `.systemextension`,
  which only a real Mac (tart/Tahoe VM or self-hosted runner) can validate.

## 3. macOS CI job that stays honest

Split it into two jobs so the verified part gates and the unverified part doesn't:

1. `rust-core` (gating): `rustup target add` host + `aarch64-apple-darwin`;
   `cargo test -p extfs-core`; explicit
   `cargo build -p extfs-core --target aarch64-apple-darwin` + `cargo check -p
   extfs-capi --target aarch64-apple-darwin`.
2. `fskit-scaffold` (best-effort, `continue-on-error`, `exit 0`): if the
   `.xcodeproj` exists, `xcodebuild … CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO`.
   A failure is expected and emits a `::warning::` that the Swift/FSKit layer is
   UNVERIFIED — never gates the run.
