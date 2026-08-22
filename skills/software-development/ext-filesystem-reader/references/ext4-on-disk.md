# ext on-disk layout (condensed, for a read-only reader)

Field offsets are relative to the structure start; ext is little-endian.
All reads must be bounds-checked (`rec_len`, `name_len`, block geometry).

## Superblock (1024 bytes at byte offset 1024)

Magic `0xEF53` @0x38; if wrong -> not an ext filesystem.
Block size = `1024 << s_log_block_size` (0x18), valid 0..=2 => 1024..4096.
s_state @0x3a: bit0 EXT2_VALID_FS(clean). Dirty / incompat&RECOVER -> reject at open.
Key offsets (byte):
- 0x04 blocks_count_lo, 0x150 blocks_count_hi (=> 64-bit total)
- 0x14 first_data_block (block number, not a byte offset)
- 0x20 blocks_per_group, 0x28 inodes_per_group
- 0x54 first_ino, 0x58 inode_size (default 256), 0xfe desc_size
- 0x5c compat, 0x60 incompat, 0x64 ro_compat
- 0x174 log_groups_per_flex

## Feature bits (the ones that matter)

INCOMPAT (0x60) — must whitelist or reject:
- 0x0002 filetype, 0x0004 recover(reject dirties), 0x0040 extents,
  0x0080 64bit, 0x0100 mmp(reject), 0x0200 flex_bg, 0x2000 metadata_csum_seed,
  0x4000 largedir(linear scan safe), 0x8000 inline_data(reject),
  0x10000 encrypt(reject), 0x20000 casefold(reject), 0x80000 orphan_file,
  0x0010 meta_bg(reject unless handled).
Compatible: 0x0004 has_journal, 0x0008 ext_attr, 0x0010 resize_inode,
  0x0020 dir_index(HTree — linear scan is a valid fallback).
RO-compat: 0x0001 sparse_super, 0x0002 large_file, 0x0008 huge_file,
  0x0010 gdt_csum, 0x0020 dir_nlink, 0x0040 extra_isize, 0x0100 quota,
  0x0200 bigalloc(reject for MVP), 0x0400 metadata_csum.

Real-world note: default `mke2fs -t ext4` sets flex_bg+64bit+extents+metadata_csum+
metadata_csum_seed+orphan_file+dir_index+has_journal. metadata_csum_seed and
orphan_file are safe to whitelist on a clean fs but MUST be rejected on a dirty
one (orphan list needs recovery).

## Group descriptor table (GDT)

Always starts at byte 2048 (immediately after the 1024-byte superblock),
regardless of block size. One descriptor per block group.
Number of groups = ceil(blocks_count / blocks_per_group).
Descriptor stride: 32 bytes, or 64 when `64bit` or `metadata_csum` is set.
Narrow (32) and wide (64) inode_table base:
- narrow: inode_table @8 (u32). wide: lo @8, hi @40 -> u64.
- block_bitmap lo @0 (hi @32 wide); inode_bitmap lo @4 (hi @36 wide).

## Inode (256 bytes typical; header 128)

- 0x00 mode (S_IFMT high nibble: reg 0o100000, dir 0o040000, lnk 0o120000)
- 0x02 uid_lo, 0x04 size_lo, 0x06..; 0x1c blocks (512-byte units), 0x1a links
- 0x18 gid_lo, 0x20 flags (extents 0x00080000, inline_data 0x10000000)
- 0x28..0x64 i_block[15] 60 bytes: legacy blockmap OR extent-tree root
- 0x6c size_high (upper 32 bits of size)
- 0x80 extra_isize; uid_hi @0x7c, gid_hi @0x7e when extra_isize >= 4
- 0x08 atime, 0x10 mtime, 0x0c ctime (i32 secs); dtime 0x14

Inode addressing: group = (ino-1)/inodes_per_group,
index = (ino-1)%inodes_per_group;
byte_offset = gdt[group].inode_table * block_size + index * inode_size.

## Legacy block map (no extents)

i_block[0..12] direct (physical block nums), then single indirect [12],
double indirect [13], triple indirect [14]. Each pointer block holds
block_size/4 entries. A physical block of 0 = hole (read zeroes).

## Extents

Root header in i_block: 0x00 magic 0xF30A, 0x02 entries, 0x04 max, 0x06 depth.
depth 0 => leaf extents; depth>0 => index entries to deeper blocks.
Leaf entry (12B): 0x00 ee_block(logical), 0x04 ee_len(u16, bit15=unwritten),
0x08 ee_start_lo, 0x06 ee_start_hi -> physical = (hi<<32)|lo.
Index entry (12B): 0x00 ei_block, 0x04 ei_leaf_lo, 0x08 ei_leaf_hi.
Cap depth (ext4 allows a few levels; reject absurd depths). Unwritten extent or
index beyond range => hole (zeroes).

## Directory records

With `filetype`: name_len u8 @6, file_type u8 @7, name @8.
Legacy (no filetype): name_len u16 @6, no type byte.
Common: inode u32 @0, rec_len u16 @4.
Validation: rec_len >= 8 and %4==0 and within block; name_len<=255;
name_len fits in rec_len. inode==0 => deleted entry (skip).
rec_len==0 would loop forever -> reject.

## Symlinks

Fast: target inline in i_block, capacity 60 + (inode_size - 128), only when
inode.blocks == 0. Slow: read the symlink inode like a file.
