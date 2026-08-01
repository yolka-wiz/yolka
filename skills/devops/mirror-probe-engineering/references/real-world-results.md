# Real-World Test Results — 6 Mirrors, July 2026

See `PLAN.md` and `ISSUE.md` in the mirava-core repo for full detail.

## Mirrors Tested

| Mirror | Country | Types Detected | Hit Rate |
|--------|---------|---------------|----------|
| mirror.freedif.org | SG | apt, arch, alpine, opensuse | 5/5 — perfect |
| hkg.mirror.rackspace.com | HK | apt, arch, epel, rocky, almalinux | 6/6 — perfect after gzip fix |
| mirror.mobinhost.com | IR | apt, arch, alpine, epel | 5/5 — perfect |
| mirrors.pardisco.co | IR | apt, alpine, docker | 4/6 — pypi/npm claimed but absent |
| docker.iranserver.com | IR | docker only | 1/1 — perfect edge case |
| mirror.rasanegaar.com | IR | (none) | 0/1 — mirror down (503) |
| repo.iut.ac.ir | IR | apt | 2/5 — repos under `/repo/` prefix |

## Bugs Found During Testing

1. **Go auto-decompresses gzip** (DisableCompression: false): Arch/Alpine validation reads decompressed body, gzip magic bytes gone. Fix: set DisableCompression: true.
2. **IUT `/repo/` prefix**: All repos under subdirectory prefix. Not a tool bug — user should provide the full path.
3. **Raspberry Pi mirror stubs**: Empty body on /npm/ gave false positive. Fix: body validation (check for "objects" key).

## Speed Test Results

| Mirror | Speed | Method |
|--------|-------|--------|
| mirrors.pardisco.co | 3.8 MB/s | apt ls-lR.gz |
| hkg.mirror.rackspace.com | 0.79 MB/s | apt ls-lR.gz |
| mirror.freedif.org | 5.5 MB/s | apt ls-lR.gz |
