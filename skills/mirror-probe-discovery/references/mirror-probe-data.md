# Mirror Probe Reference Data

Empirical probe results from real-world testing (July 2026).

## Chabokan — `https://mirror2.chabokan.net/`

```
Root:                200  HTML page
/ubuntu/:            502  (not a directory listing)
/ubuntu/dists/noble/Release:   200  255KB  (Origin: Ubuntu, Components: main restricted universe multiverse)
/ubuntu/dists/jammy/Release:   200  269KB
/ubuntu/dists/focal/Release:   200  263KB
/ubuntu/dists/bookworm/Release:    502
/debian/dists/bookworm/Release:    200  (user confirmed)
/v2/:                200  {"name": "Chabok Mirror Docker Registry"}
/simple/:            404
/pypi/simple/:       200  (user confirmed — non-standard path)
/packages.json:      404
/composer/:          200  (user confirmed)
/npm/:               200  (user confirmed)
/core/os/x86_64/core.db:    404
```

**Detected**: apt (Ubuntu noble, jammy, focal), Docker Registry, PyPI at `/pypi/`, Composer at `/composer/`, npm at `/npm/`

---

## ArvanCloud — `http://mirror.arvancloud.ir/`

```
Root:                301  -> https://www.arvancloud.ir/dev/linux-repository (marketing page)
Root -L:             200  (at marketing page)
/ubuntu:             200  HTML directory listing
/ubuntu/:            301
/ubuntu/dists/noble/Release:   200  255KB
/ubuntu/dists/jammy/Release:   200  269KB
/ubuntu/dists/focal/Release:   200  263KB
/ubuntu/ls-lR.gz:    200  11.9MB  (excellent speed test target)
/debian:             200  (user confirmed)
/centos/:            404
/v2/:                503
/alpine/:            404
/alpine/v3.23/:      200  (user confirmed — version in path!)
/archlinux/core/os/x86_64/acl-2.4.0-1-x86_64.pkg.tar.zst: 200  (user confirmed — no dir listing but files exist)
```

**Detected**: apt (Ubuntu noble, jammy, focal), Debian, Alpine (v3.23), Arch (files exist but no dir listing)
**Not detected from main URL**: Docker (separate subdomain `docker.arvancloud.ir`)

---

## Rackspace — `https://hkg.mirror.rackspace.com/`

```
Root:                200  Apache directory listing (45+ links)
/ubuntu/dists/noble/Release:   200
/debian/dists/bookworm/Release:   200
/debian-security/dists/bookworm-security/Release:   200
/archlinux/core/os/x86_64/core.db:    200
/archlinux/extra/os/x86_64/extra.db:  200
/epel/9/Everything/x86_64/repodata/repomd.xml:   200
/epel/10/Everything/x86_64/repodata/repomd.xml:  200
/centos-stream/9-stream/BaseOS/x86_64/repodata/repomd.xml:  404  (dir exists, repomd does not)
/centos-stream/9-stream/:  Apache listing (BaseOS, AppStream, CRB dirs present)
/v2/:                404
```

**Root links include**: CPAN, CentOS, ELRepo, FreeBSD, MySQL, almalinux, archlinux, centos-stream, debian, debian-security, docker-ce, epel, fedora, freebsd, gentoo, linuxmint, mariadb, nginx-org, openSUSE, opensuse, oraclelinux, rocky, slackware, ubuntu, ubuntu-releases, vmware

---

## MIT — `https://mirrors.mit.edu/`

```
Root:                200  Custom HTML table (25+ links)
/ubuntu/dists/noble/Release:   200
/debian/dists/bookworm/Release:   200
/archlinux/core/os/x86_64/core.db:    200
/epel/9/Everything/x86_64/repodata/repomd.xml:   200
/centos-stream/9-stream/BaseOS/x86_64/repodata/repomd.xml:  404
/v2/:                404
```

**Root links include**: ArchLinux, CentOS, CPAN, CTAN, Cygwin, Debian, Debian backports, Fedora, Fedora EPEL, FreeBSD, Gentoo, KDE, Kali, LibreOffice, MX Linux, OpenBSD, ParrotOS, Raspbian, Tails, Tor, Ubuntu, Ubuntu CD images

---

## TUNA — `https://mirrors.tuna.tsinghua.edu.cn/`

```
Root:                200  JS-rendered (has /legacy_index as plain HTML fallback)
/ubuntu/dists/noble/Release:   200
/debian/dists/bookworm/Release:   200
/debian-security/dists/bookworm-security/Release:   200
/archlinux/core/os/x86_64/core.db:    200
/alpine/v3.20/main/x86_64/APKINDEX.tar.gz:  200
/epel/9/Everything/x86_64/repodata/repomd.xml:   200
/opensuse/tumbleweed/repo/oss/repodata/repomd.xml:    200
/centos-stream/9-stream/BaseOS/x86_64/repodata/repomd.xml:  404
/v2/:                404
```

**legacy_index links (100+)**: adobe-fonts, alpine, anaconda, apache, archlinux, archlinuxarm, armbian, centos, centos-stream, CPAN, CRAN, crates.io-index, CTAN, debian, debian-security, deepin, docker-ce, epel, fedora, gentoo, kali, opensuse, rocky, ubuntu, and many more

---

## xTom Estonia — `https://mirrors.xtom.ee/`

```
Root:                200  Styled page with <a> links (~30 repos)
/ubuntu/dists/noble/Release:   200
/debian/dists/bookworm/Release:   200
/debian-security/dists/bookworm-security/Release:   200
/archlinux/core/os/x86_64/core.db:    200
/archlinux/extra/os/x86_64/extra.db:  200
/alpine/v3.20/main/x86_64/APKINDEX.tar.gz:  200
/epel/9/Everything/x86_64/repodata/repomd.xml:   200
/centos-stream/9-stream/BaseOS/x86_64/repodata/repomd.xml:  404
/v2/:                404
```

**Root links include**: almalinux, alpine, archlinux, centos-stream, debian, debian-security, docker-ce, epel, fedora, kde, mariadb, nginx, postgresql, proxmox, rocky, ubuntu, ubuntu-releases
