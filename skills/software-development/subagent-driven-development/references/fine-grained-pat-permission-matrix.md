# Fine-grained PAT permission matrix (GitHub)

Which permission-matrix row gates which operation. Fine-grained PATs
(Settings → Developer settings → Fine-grained tokens,
https://github.com/settings/tokens?type=beta) scope **per repository**; the
token NAME means nothing — an "admin" key is only as powerful as the boxes
ticked in its matrix.

## Operation → permission

| Operation | Fine-grained row | Classic scope |
|---|---|---|
| `git push`, create/delete branches | **Contents: Read and write** | `repo` |
| `gh pr create`, reviews, comments | **Pull requests: Read and write** | `repo` |
| `gh run list` / `run view` (CI status) | **Actions: Read** | `repo` + `workflow` |
| `gh release create` (Release object) | **Contents: Read and write** (same row as push!) | `repo` |
| `gh secret set` / Actions secrets | **Actions: Read and write** + Secrets | `repo` + `workflow` |
| Issues, repo metadata reads | Issues: Read / Contents: Read | `public_repo` / `repo` |
| Branch protection / ruleset admin | **Administration: Read and write** | `repo` + admin role |
| Create release assets (upload) | **Contents: Read and write** (release + asset uploads) | `repo` |

## Failure signatures (403 = missing scope, not bad token)

- `HTTP 403: Resource not accessible by personal access token
  (createPullRequest)` → missing **Pull requests: R/W**
- Same error on `.../releases` → missing **Contents: write** even though PR
  creation works (the classic trap: PRs succeed, releases fail, push succeeds)
- `gh api .../releases` returning 200 proves READ only, never write

## Fix: edit the existing token, do NOT regenerate

Permission edits apply to the CURRENT token string — the stored
`~/.config/gh/hosts.yml` value keeps working without re-pasting. Only
regenerate if GitHub forces it. After the user says "done", retry the exact
failing command, then verify with a read (`gh run list`, `gh release list`).

## Probe the scope, don't guess

```bash
# Contents:write probe — 201 = write granted, 403 = read-only token
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $(gh auth token)" \
  -X PUT -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<owner>/<repo>/contents/__perm_probe__.txt" \
  -d '{"message":"perm probe","content":"cGVybQ=="}'
# clean up a 201: DELETE the probe with the returned sha
```

## Tag-vs-Release nuance

The TAG is pushed with plain `git push origin <tag>` (no API scope needed) —
so the release commit is public even when the Release OBJECT is blocked by a
403. UI fallback when the token can't create the Release: **Releases → Draft a
new release → pick the pushed tag** — the release notes text is ready to paste
and the workflow unblocks without any token change.

Hit 2026-08-07 (albdf 0.2.0): fine-grained PAT named "admin" created PRs and
pushed tags, but `gh release create` 403'd; the missing row was
Contents:write. Fixed by editing the existing token's Contents row (no new
token, no re-paste) — the 403 disappeared and the release + assets went up in
one command.
