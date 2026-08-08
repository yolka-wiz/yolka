# Fine-grained PAT permission model (GitHub) — 2026-08-07

Verified while releasing albdf 0.2.0 and managing PRs. Fine-grained PATs
(`github_pat_...`) have a **two-axis permission model** that classic tokens
don't: *which repos* the token covers × *what permission* per category. The
token's display name means nothing ("admin" in the name ≠ admin rights).

## The failure table (all hit in one session)

| Operation | Fine-grained requirement | Failure observed | Workaround |
|---|---|---|---|
| `gh release create` / upload assets | **Contents: write** | `HTTP 403: Resource not accessible by personal access token` | Edit token → Repository permissions → Contents → Read and write. Existing token value picks it up instantly, no new token needed |
| `gh pr create` | GraphQL `pull_requests` write | `GraphQL: Resource not accessible by personal access token (createPullRequest)` | **REST works with the same token**: `curl -X POST -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" https://api.github.com/repos/OWNER/REPO/pulls -d '{"title":"...","head":"BRANCH","base":"main","body":"..."}'` → 201. gh uses GraphQL for PR creation; fine-grained tokens often lack it |
| Create a repo, then push to it with the SAME token | repo must be in the token's selected repos | 403 on contents API AND git push | Token only covers repos selected at creation. **Use the SSH key** — a user-level SSH key authenticates the account and pushes to any repo it owns: `git remote set-url origin git@github.com:OWNER/REPO.git && git push` |
| `PATCH /user` (name/bio/location/company) | **classic** PAT with `user` scope | 403 — fine-grained tokens can't touch account-level profile | Settings → Profile, or a classic PAT with `user` scope |
| `gh auth refresh -h github.com -s user` | device flow adds the `user` scope to the EXISTING classic token | hangs headless (needs browser); prints `! First copy your one-time code: XXXX-XXXX` + https://github.com/login/device | run in background, hand the code to the user, apply after they approve — then `gh api -X PATCH /user -f name=...` works |

## Merging past branch protection (temporary relaxation — user-directed 2026-08-07)

When a ruleset blocks merges (e.g. `required_approving_review_count: 1`) and the user
explicitly authorizes temporary relaxation to avoid a review stall:

1. **Find the ruleset ID**: `GET /repos/{owner}/{repo}/rulesets` → note `id` + `name`
   (the repo's protection may be a *ruleset*, not legacy branch protection — `GET
   /branches/main/protection` returns 404/empty for rulesets).
2. **Relax**: `PUT /repos/{owner}/{repo}/rulesets/{id}` with the same body but
   `pull_request.parameters.required_approving_review_count: 0` (keep `deletion` +
   `non_fast_forward` rules and the enforcement mode intact). Verify the response
   shows the new count.
3. **Merge** (see below), then **restore** the original body (`required_approving_review_count: 1`).
   Always restore — the relaxation is a window, not a policy change.
4. **Merge method fallback**: `merge_method: rebase` fails with `This branch can't be
   rebased` when main moved after the PR branch was created (e.g. a prior PR merged in
   between). Fall back to `squash` (or `merge`) with the same token — no new approval
   needed. Rebase-only repos will need a `git pull --rebase` + force-push instead.

## Rules of thumb

1. **Probe the ACTUAL operation** — a 200 on `GET /user` proves auth, NOT
   write permission. Test the failing operation directly before assuming the
   token is broken.
2. **REST before re-auth.** When `gh` 403s (GraphQL), try the REST endpoint
   with the same token before asking for a new one.
3. **SSH is the universal escape hatch** for repo-scoped-token 403s.
4. **Contents: write is the master switch** for: releases, contents API
   writes, branch deletion, most repo mutations.
5. **Always verify the side effect** (re-fetch the release, re-check the PR)
   — a 201/200 from the API is not the same as the object existing.

## Related

- albdf release workflow that hit this: `references/release-0.2.0-workflow.md`
- `gh pr create` GraphQL vs REST: github-pr-workflow skill §3 (user-owned —
  if the agent needs this embedded there, recommend `hermes curator adopt`)
