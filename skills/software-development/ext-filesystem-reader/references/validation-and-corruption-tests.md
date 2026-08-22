# Validation-pass tests: byte-level corruption recipe + mke2fs harness

Session-proven recipe for testing a reader's `validate()`/bounds pass against
real `mke2fs`-built images and for direct on-disk byte corruption. Worked in
`extfs-macos` (Rust core, `MemoryBlockDevice`).

## Security-critical: mke2fs may be off the shell PATH

`mke2fs` is often in `/sbin` or `/usr/sbin`, which a non-login agent shell's
PATH omits — `command -v mke2fs` returns 127 even though the binary exists.
Without a fix you get silent test SKIPs. Inside each integration test (or a
helper run before every `Command`), append the dirs if missing:

```rust
fn ensure_tools() {
    let path = std::env::var("PATH").unwrap_or_default();
    if !path.split(':').any(|p| p == "/sbin" || p == "/usr/sbin") {
        std::env::set_var("PATH", format!("{path}:/sbin:/usr/sbin"));
    }
}
```

Then use `Command::new("mke2fs")` with explicit args and verify the exit status
(`.status().map(|s| s.success())`). Parsing bytes back:
`std::fs::read(&img)`.

## Building an image at a chosen block size

```rust
Command::new("mke2fs")
    .args(["-q", "-t", "ext4", "-F", "-b", &block_size.to_string()])
    .arg(path)
```

Create the target file first with `File::set_len(n)` (sparse, e.g. 32 MiB), then
run mke2fs.

## On-disk byte offsets for corruption (values verified against mke2fs images)

These byte offsets are the *only* things hard to re-derive by hand; get them
right or the corruption silently misses (e.g. patching byte 2048 on a
4096-block image does nothing because the GDT isn't there).

Superblock (always at byte 1024, 1024 bytes long):
- `inodes_count`     @ 0x00
- `blocks_count_lo`  @ 0x04   (combine with hi @ 0x150 for 64-bit)
- `first_data_block` @ 0x14
- `log_block_size`   @ 0x18   (block_size = 1024 << log)
- `blocks_per_group` @ 0x20
- `inodes_per_group` @ 0x28
- `inode_size`       @ 0x58
- `desc_size`        @ 0xfe

Group descriptor table (NOT a fixed offset — see SKILL.md pitfall #4):
- `GDT_byte_offset = (first_data_block + 1) * block_size`
  (= 2048 for 1 KiB blocks, = block_size for 4096 blocks).
- Within descriptor 0, low 32-bit fields are at GDT+0 (`block_bitmap`),
  GDT+4 (`inode_bitmap`), GDT+8 (`inode_table`).
- To corrupt: `bytes[gdt + 8..gdt + 12].copy_from_slice(&u32::MAX.to_le_bytes())`
  → huge block number (still no u64 overflow for 32-bit lo). Zeroize
  `block_bitmap` → non-zero check fires.

## Assertions that prove validate() works, not just that it returns Err

- Corrupt from a **real valid image** (so you know the baseline opens cleanly),
  then assert `Err(ExtfsError::Corrupt(msg))` where `msg` names the field
  (`contains("inode_table")`, `contains("block_bitmap")`).
- Assert an unmodified image opens (`Ok`) — this is the anti-false-positive
  guard: validation must never reject valid images.
- Run the all-valid check across **at least 1024 and 4096** block sizes; this is
  what catches the hard-coded-GDT-offset bug.
- A panic in any of these tests fails them, so `is_err()`/`Err(...)` asserts are
  implicitly also "no panic" checks. To be explicit, use `std::panic::catch_unwind`.
- If `Filesystem` has no `Debug`, make the open helper return
  `Result<(), ExtfsError>` (discard the fs on Ok) so test `panic!` formatting
  doesn't need `Debug` on the fs type.
