---
name: rust-c-ffi
description: Build panic-safe Rust↔C FFI boundaries — #[repr(C)] types, opaque handles, callback vtables, and catch_unwind that never lets a panic unwind into C. Use when exposing Rust as a cdylib/staticlib, writing C headers that mirror Rust types, or calling Rust callbacks from C.
version: 1.0.0
author: Hermes curator
license: MIT
metadata:
  tags: [ffi, c-abi, rust, catch-unwind, external-c]
  related_skills: [ext-filesystem-reader, coding-workflow]
---

# Rust ↔ C FFI (panic-safe boundary)

## When to Use

Use when you must expose Rust to C/foreign code, or call Rust callbacks from C:
building a cdylib/staticlib + C header, writing `#[repr(C)]` boundary types, or
guarding a Rust core so a panic can never unwind across the C boundary (Swift/ObjC,
FUSE, Python ctypes, FFI test hooks). Also when a panic in an `extern "C"` fn aborts
despite `catch_unwind`.

Pattern for a narrow C ABI over a Rust core (e.g. for Swift/FSKit/FUSE/other-language
adapters). "Never let a Rust panic cross the C boundary" is the central invariant.

## THE critical pitfall: `extern "C"` is non-unwinding

In modern Rust, a function declared `extern "C"` is **non-unwinding**. If it panics —
even if the caller wraps the call in `catch_unwind` — the runtime aborts with:

```
panic in a function that cannot unwind
... thread caused non-unwinding panic. aborting. (SIGABRT)
```

`catch_unwind` CANNOT catch it. This is the #1 gotcha when a Rust-implemented
`extern "C"` callback panics (real external C never panics, but Rust test hooks and
callback layers do).

**Fix:** declare callback / function-pointer types as `extern "C-unwind"` (stable
since Rust 1.71; identical machine ABI to `extern "C"`, just permits unwinding so a
panic can reach your `catch_unwind`):

```rust
#[repr(C)]
#[derive(Clone, Copy)]
pub struct MyOps {
    pub read_at: Option<unsafe extern "C-unwind" fn(ctx: *mut c_void, off: u64, dst: *mut u8, n: usize) -> i32>,
    pub ctx: *mut c_void,
}
```

Plain `extern "C"` on an **exported** function is fine as long as the *body itself*
can't panic (e.g. it only derefs pointers and calls guarded internal fns). Only the
*function-pointer fields* that get invoked as callbacks need `C-unwind`.

## Layer the guards

Two layers so a panic can't escape even through the byte-serving vtable:

1. **Outer guard** — wrap every exported function body in `catch_unwind`:

```rust
fn guarded<T>(f: impl FnOnce() -> T) -> Result<T, ()> {
    catch_unwind(AssertUnwindSafe(f)).map_err(|_| ())
}
// export: guarded(|| { ... }) .unwrap_or(EPANIC)
```

2. **Inner guard** — wrap the C callback invocation (e.g. the `read_at` call) in its
   own `catch_unwind`, mapping a panic to `Err(Io)`. Do NOT wrap `len()`/other simple
   accessors in the inner guard — leaving one unwrapped lets you write a test that
   provokes the OUTER guard → `EPANIC`, proving both layers.

## Error-code convention

- `0 = OK`, **negative = error**, positive = operation-specific (e.g. readdir returns
  `1` when the app callback requested early stop).
- Provide an `extern "C"`-matching enum: `#[repr(i32)] enum` with negative discriminant
  values.
- Map internal errors to codes lossily with a small `match` table (NotFound→ENOENT,
  NotDirectory→ENOTDIR, IsDirectory→EISDIR, Io→EIO, ...). Add a dedicated `Panic = -N`
  code returned by the outer guard.
- `ssize_t` ↔ `isize`; `size_t` ↔ `usize`.

## Other mechanics

- **Opaque handle:** keep a zero-sized `#[repr(C)] pub struct ExtfsHandle { _private: [u8;0] }`
  as the C-visible type; store the real data in an internal struct. `open` → `Box::into_raw(...) as *mut OpaqueHandle`; exports cast the pointer back; `close` → `drop(Box::from_raw(...))`.
- **Ownership must be documented** in the header + Rust: chose "`open` takes a copy of
  the ops struct, but `ctx` is caller-owned and must outlive the handle; `close` never
  frees `ctx`." Write it down explicitly in the C header.
- Keep `#[repr(C)]` structs in lockstep with the C header; the `#[repr(C)]` struct must
  be `Copy` if you copy it from the pointer (`Box::new(*ops)`).
- Bounds-check callback reads against `len()` and write outputs atomically at the end
  so a failure never leaves the caller's buffer half-populated.

## Verification / tests

- Mirror the header with `#[repr(C)]` types and exercise every export.
- Write a **panic-containment test**: a block_ops whose `read_at`/`len` deliberately
  panics; assert the exported fn RETURNS a code (never aborts). A `run_open_success`
  then flip a flag then call → distinct code (inner guard → Io; outer guard → EPANIC).
- Corrupt-input test: feed all-0xFF via a garbage `read_at` and call every export —
  the assertion is that it returns at all (no abort), not specific values (garbage that
  still parses may "succeed").
- **Parallel-test gotcha:** a temp dir named from `std::process::id()` + a fixed tag
  collides across tests running in parallel (they delete each other's files). Make dir
  names unique per invocation with a `static AtomicU64` counter.

See `references/extfs-capi-recipe.md` for a complete worked example (file-backed vtable,
error table, panic test).

## Cross-compiling the C ABI for Apple targets from Linux (and bridging to Swift)

When the cdylib/staticlib is destined for a Swift/FSKit (or ObjC) macOS adapter but
you only have a Linux box: `rustup target add aarch64-apple-darwin` then
`cargo build -p <pure-std-core> --target aarch64-apple-darwin` and
`cargo check -p <capi> --target aarch64-apple-darwin` **both succeed** without an
Apple SDK. The `cdylib`/`staticlib` **link** of the capi fails on Linux
(`cc: unrecognized option '-arch'`) because there is no Apple linker — that is
environment-driven, not a code bug, so report it as "compiles, link-limited"
and validate the actual Apple artifact on a real Mac/VM/runner.
Remember the FFI must still be built with `RUSTFLAGS="-C panic=unwind"` so the
`catch_unwind` containment holds for the shipped Apple binary.

Swift bridging is done with a bridging header or `module.modulemap` that includes
the shared C header **by path relative to the crate** (a Linux LSP may flag the
include as missing — expected, resolves at Xcode build time), and the
`block_ops`-style vtable is mirrored with `@convention(c)` funcs recovering the
backend from an `Unmanaged` ctx. When the Swift cannot be compiled here, write it
correct-by-construction, tag uncertain C-importer/FSKit APIs `TODO(swift-cabi)`/
`TODO(FSKit)`, and **stage but do not commit** the unvalidated Swift layer so it
never mixes into verified history.

See `references/apple-target-and-swift-bridge.md` for the exact commands
(success/link-limited matrix), the Swift scaffold rules, and a two-job macOS CI
layout that keeps the verified Rust core gating while the Swift FSKit build stays
best-effort/non-gating.
