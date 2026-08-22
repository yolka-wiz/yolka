# extfs-capi worked example (panic-safe C ABI over a filesystem core)

Concrete realization of the `rust-c-ffi` pattern, in a real crate
(`crates/extfs-capi` over a read-only ext2/3/4 core). Serves as a copy-and-modify
recipe. Cargo crate-type: `["cdylib", "staticlib", "rlib"]`.

## File layout
```
include/extfs.h      # C header mirroring the Rust types
src/types.rs         # #[repr(C)] types + error enum
src/lib.rs           # exported functions + guards
tests/capi.rs        # mke2fs-backed image tests + panic-containment tests
```

## Error enum (0=OK, negative=error)
```rust
#[repr(i32)]
pub enum ExtfsErrorCode {
    Ok = 0, Io = -1, Corrupt = -2, UnsupportedFeature = -3, NotFound = -4,
    NotDirectory = -5, IsDirectory = -6, PermissionDenied = -7, ReadOnly = -8,
    InvalidName = -9, Overflow = -10, JournalRecoveryRequired = -11,
    NotExt = -12, Panic = -13,
}
```

## Error map (lossy table)
`Io→-1, Corrupt→-2, UnsupportedFeature→-3, NotFound→-4, NotDirectory→-5,
IsDirectory→-6, PermissionDenied→-7, ReadOnly→-8, InvalidName→-9, Overflow→-10,
JournalRecoveryRequired→-11, NotExt→-12`; outer guard returns `Panic=-13`.

## Block device vtable
```rust
#[repr(C)] #[derive(Clone, Copy)]
pub struct ExtfsBlockOps {
    pub len: Option<unsafe extern "C-unwind" fn(*mut c_void) -> u64>,
    pub logical_sector_size: Option<unsafe extern "C-unwind" fn(*mut c_void) -> u32>,
    pub read_at: Option<unsafe extern "C-unwind" fn(*mut c_void, u64, *mut u8, usize) -> i32>,
    pub ctx: *mut c_void,
}
// read_at returns 0 on success; must not partially mutate dst on failure.
```

The `Block` adapter implements the core's trait:
```rust
impl Block for OpsBlock {
    fn len(&self) -> u64 { /* call ops.len(ctx) */ }
    fn read_exact_at(&self, off, dst) {
        let end = off.checked_add(dst.len() as u64).ok_or(Overflow)?;
        if end > self.len() { return Err(Io); }        // len() NOT inner-guarded
        catch_unwind(AssertUnwindSafe(|| read_at(ctx, off, dst.as_mut_ptr(), dst.len())))
            .map(|rc| if rc == 0 { Ok(()) } else { Err(Io) })
            .unwrap_or(Err(Io))                        // inner guard: packet->Io
    }
}
```
Leaving `len()` outside the inner guard is deliberate: a panicking `len()` bubbles to
the outer export guard → `Panic(-13)`, which is how you test the outer layer.

## Opaque handle
```rust
#[repr(C)] pub struct ExtfsHandle { _private: [u8; 0] }   // C-visible zero-sized
struct Handle { fs: Filesystem<OpsBlock> }                 // internal real data
// open:  Box::into_raw(Box::new(Handle{..})) as *mut ExtfsHandle
// stat:  let h = &*(handle as *const Handle);
// close: drop(Box::from_raw(handle as *mut Handle));  // no-op on NULL
```

## Exports
`extfs_open(ops) -> *mut ExtfsHandle` (copies ops; NULL on failure/invalid),
`extfs_close(handle)`, `extfs_stat_inode(h,ino,*stat) -> i32`,
`extfs_lookup(h,parent,name,len,*ino) -> i32`,
`extfs_readdir(h,ino, cb, cb_ctx) -> i32` (cb returns int: 0=continue, nonzero=stop→1),
`extfs_read(h,ino,off,buf,len) -> isize`, `extfs_readlink(h,ino,buf,len) -> isize`.
Every function body inside `guarded(...)`, `unwrap_or(Panic)`.

## Tests: generate a real image by shelling out (allowed in tests)
```rust
Command::new(mke2fs).args(["-q","-t","ext4","-b","1024","-F"])
    .arg(&img).arg("32768")   // 32768 * 1KiB = 32MiB sparse file (set_len first)
Command::new(debugfs).args(["-w","-R", &format!("write {payload} hello.txt"), &img])
Command::new(debugfs).args(["-w","-R", &format!("symlink hello_link hello.txt"), &img])
```
Locate tools on PATH with `/usr/sbin`, `/sbin` fallbacks; skip if absent. Root inode is
`2`; `mke2fs` also creates `lost+found` in the root, so readdir assertions should check
"contains expected names" rather than exact equality.

### debugfs gotchas (verified)
- **`symlink` arg order is `<link_name> <target>`** (first arg = name). Passing them
  swapped gives `Ext2 file already exists while creating symlink "<name>"`.
- async: inode numbers are assigned incrementally; don't hardcode the file inode —
  resolve it via `lookup` in the test.

## Panic-containment tests
- A file-backed ctx with `panic_len` / `panic_read` bool flags toggled after a clean open.
  - `panic_read` on open → inner guard → `open` returns NULL (no abort).
  - `panic_read` after open → stat returns `Io(-1)`.
  - `panic_len` after open → outer guard → stat returns `Panic(-13)`.
- Corrupt test: overwrite the ctx bytes with `0xFF` after open, call every export with
  `let _ =` — reaching the end proves no abort/unwind (garbage may still parse OK).
- Deterministic error checks on the healthy image: `stat(u64::MAX)` → `NotFound(-4)`;
  `read(dir_inode,...)` → `IsDirectory(-6)`.

## Parallel-test temp-dir uniqueness
Use a `static AtomicU64` counter in the dir name, not just `process::id()+tag` —
tests run in parallel and delete each other's dirs otherwise.
