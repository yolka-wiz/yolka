---
name: mirror-probe-engineering
description: 'Probe mirrors to auto-detect repo types.'
---

# Mirror Probe Engineering

Design probes that auto-detect what repo types a mirror serves, without prior knowledge of the mirror's internal layout.

## The Core Pattern

```
For each repo type, find ONE signature path that:
1. Is UNIVERSAL across all mirrors serving that type
2. Returns content that ONLY that type would serve (body validation)
3. Avoids relying on directory listings (mirrors often 502/redirect on root)
4. Works with a simple GET + 200 check (no complex protocol)

Then:
- Run ALL probes in PARALLEL with a shared context timeout
- Validate response BODY, not just status code
- Fall back to HTML root scraping for distros without universal paths
```

## Universal Signature Paths (proven across 6+ real mirrors)

| Type | Probe Path | Body Validation |
|------|-----------|-----------------|
| APT Ubuntu | `/ubuntu/dists/{suite}/Release` | `Origin:`, `Components:`, `Architectures:` headers |
| APT Debian | `/debian/dists/{suite}/Release` | same |
| Arch/Pacman | `/archlinux/core/os/x86_64/core.db` | gzip magic bytes `\x1f\x8b` |
| Alpine | `/alpine/v{ver}/main/x86_64/APKINDEX.tar.gz` | gzip magic bytes |
| Docker | `/v2/` | JSON body (any) or 401 |
| EPEL | `/epel/{ver}/Everything/{arch}/repodata/repomd.xml` | XML `<repomd>` root |
| Rocky Linux | `/rocky/{ver}/BaseOS/{arch}/os/repodata/repomd.xml` | XML `<repomd>` |
| AlmaLinux | `/almalinux/{ver}/BaseOS/{arch}/os/repodata/repomd.xml` | XML `<repomd>` |
| OpenSUSE | `/opensuse/tumbleweed/repo/oss/repodata/repomd.xml` | XML `<repomd>` |
| PyPI | `/simple/` or `/pypi/simple/` | HTML `<a href` pointing to relative paths |
| npm | `/-/v1/search?text=test&size=1` or `/npm/...` | JSON with `"objects"` key |
| Composer | `/packages.json` or `/composer/packages.json` | JSON with `"packages"` or `"metadata-url"` |

## Go Implementation Checklist

1. **HTTP client**: Set `DisableCompression: true` — Go auto-decompresses gzip responses, which strips magic bytes before your validation code sees them
2. **Context per probe**: Shared context with `context.WithTimeout` — all probes in parallel with one deadline
3. **Body validation**: Read only first 64KB of body. A `validate([]byte) bool` function per type prevents false positives from generic nginx directory listings
4. **Speed test**: One measurement is enough per mirror (same IP → same speed). Prioritise APT's `ls-lR.gz` (largest), then Docker, then fallback to signature file
5. **HTML scraping**: For root pages that return HTML with directory links — extract `<a href="...">` paths and check against known distro names. Only probe paths that appear in the HTML.

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Go auto-decompresses gzip | Arch/Alpine never detected despite 200 | `DisableCompression: true` |
| Directory listing not available | `/ubuntu/` returns 502, but `/ubuntu/dists/noble/Release` works | Probe deep paths directly, never rely on directory listings |
| Root redirects | Root 301 → marketing page, but `/ubuntu/...` works fine | Don't follow root redirect for content discovery |
| Timeout too short for all probes | Some types missed on slow mirrors | Increase `defaultProbeTimeout` or make it configurable |
| Empty body stubs | `/npm/` returns 200 with 0 bytes → false positive | Validate body content, not just status code |

## User Preferences (this user)

- Real-world testing REQUIRED before accepting algorithmic claims
- Gives specific actionable corrections — take them literally
- Clearly defines scope boundaries — stay within them
- Prefers two-option framework with tradeoffs before commitment
- Values simplicity over architecture purity
- Uses `delegate_task` subagents for parallel multi-mirror verification

## References

See `references/` in this skill directory for:
- `real-world-results.md` — 6-mirror test results and what was learned
- `rpm-discovery.md` — how to find RPM probe paths for new distros
