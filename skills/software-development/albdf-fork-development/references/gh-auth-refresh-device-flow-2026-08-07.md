# gh auth refresh device-flow + API permission probes — 2026-08-07

Verified while trying to set GitHub profile fields (PATCH /user) with a classic
PAT that lacked the `user` scope. Complements
`references/fine-grained-pat-permissions-2026-08-07.md` (the failure table for
fine-grained tokens); this file records the OPERATIONAL traps of the
scope-refresh flow and of API permission probes.

## Adding the `user` scope to an existing classic token

`PATCH /user` (name/bio/location/company) requires a classic PAT with the
`user` scope. Fine-grained tokens cannot touch account-level profile settings
(403 `Resource not accessible`). The fix is `gh auth refresh -h github.com -s
user`, which opens a device-flow that extends the EXISTING token — the flow
WORKS but has three traps:

1. **Never pipe the refresh through `tail`/`tee` in the background.**
   `gh auth refresh -h github.com -s user 2>&1 | tail -3` buffers ALL output,
   so the one-time code is invisible until the process exits — which never
   happens while it waits for browser approval. Run it pipe-free
   (`gh auth refresh -h github.com -s user 2>&1` or plain) so the code
   streams to the process log immediately, then read it with
   `process log` / `process poll`.
2. **After the user approves in the browser, gh asks a SECOND prompt:
   `? Authenticate Git with your GitHub credentials? (Y/n)`.**
   The token write happens only AFTER this prompt is answered. Killing the
   process while the prompt is pending discards the entire scope update —
   `gh auth status` still shows the old scopes. Pre-answer it so the flow
   completes unattended: run with stdin pre-fed, e.g.
   `gh auth refresh -h github.com -s user <<< "n"` (answer `n` when the
   repo's git operations use SSH; the refresh only needs to extend the API
   token, not reconfigure git). PTY submits of the answer are unreliable
   here; the heredoc is the reliable path.
3. **Verify scopes before AND after** with
   `gh auth status | grep -i "token scopes"`. A 200 on `GET /user` proves
   auth, NOT that the `user` scope landed. Only after `PATCH /user` stops
   returning `This API operation needs the "user" scope` (404/403) is the
   field update possible. When the device-flow keeps failing, the 30-second
   fallback is: user sets Settings → Profile manually with the prepared
   values — never claim the profile was updated via API without verifying
   the GET shows the new fields.

## API permission probes create REAL commits — probe on a scratch branch

Testing "can this token write?" via the contents API
(`PUT /repos/OWNER/REPO/contents/__probe__.txt`) is itself a MUTATING
operation: it creates a real commit on the default branch, and the cleanup
DELETE creates a second one. Hit 2026-08-07: `perm probe` + `remove probe`
commits landed on albdf main (cosmetic but noisy; the format gate's
authored-file list then includes the probe until the delete commit lands).

To test write access without polluting history:
- Probe in a scratch throwaway repo, or on a scratch branch that gets
  deleted after the probe.
- Or use a non-committing check first: `GET /repos/OWNER/REPO/contents/`
  succeeds with read, and the repo object's `permissions.push` field tells
  you push access without mutating anything.
- If a probe commit DID land on a protected main, clean it up with a
  follow-up delete commit (what happened here) or a force-push rewrite
  only with explicit user sign-off.
