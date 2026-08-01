# RPM Distro Probe Path Discovery

## The Pattern

RPM-based distros (Rocky, AlmaLinux, CentOS Stream, Fedora) use `repodata/repomd.xml` as their signature file. The challenge is finding the correct path prefix, which varies by distro and version.

## Verified Working Paths

| Distro | Path Pattern | Verified On |
|--------|-------------|-------------|
| Rocky Linux | `/rocky/{ver}/BaseOS/{arch}/os/repodata/repomd.xml` | Rackspace, xTom |
| AlmaLinux | `/almalinux/{ver}/BaseOS/{arch}/os/repodata/repomd.xml` | Rackspace, xTom |
| EPEL | `/epel/{ver}/Everything/{arch}/repodata/repomd.xml` | All 4 mirrors |
| CentOS Stream | `/centos-stream/{ver}-stream/BaseOS/{arch}/os/` — directories exist but repomd consistently 404 | Not available |
| Fedora | `/fedora/linux/releases/{ver}/Everything/{arch}/os/repodata/repomd.xml` — only works on official Fedora mirrors behind CDN | Not on general mirrors |

## Robuster Approach Than Guessing Paths

For RPM distros on unknown mirrors, the **directory listing recursion** approach works:

1. Check if the distro directory exists: `/{distro}/` → 200
2. If 200, list it and look for `{ver}/` or `releases/{ver}/` subdirectories
3. Recurse into `{ver}/BaseOS/{arch}/` and check for `os/` or `repodata/`
4. From the listing, find the actual path to `repodata/repomd.xml`

This was how the `/os/` subdirectory was discovered for Rocky and AlmaLinux — the directory listing showed `os/` inside `BaseOS/x86_64/`, and the expected repomd path without `os/` returned 404.

## What Doesn't Work

- Guessing flat paths like `/{distro}/{ver}/BaseOS/x86_64/repodata/repomd.xml` — the `os/` subdirectory is required but easy to miss
- Assuming the same version numbering scheme (Rocky/Alma use 8/9/10, Fedora uses 39/40/41, CentOS Stream uses 9-stream/10-stream)
- HTML root scraping alone — it finds the distro name but not the package repo path
