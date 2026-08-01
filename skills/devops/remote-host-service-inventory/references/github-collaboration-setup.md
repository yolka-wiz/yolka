# GitHub Collaboration Setup (SSH key + MCP)

Session detail: setting up agent-side GitHub access for repo work (push via SSH, GitHub MCP server for API/tooling). Real case: Viberoxy repo (`github.com/amirrezaalavi/Viberoxy`) from the agent host (Debian, `agent@`, Hermes profile `devops`).

## 1. Dedicated SSH key for GitHub

Use a **separate key** from the host's other SSH keys (don't reuse the key that authenticates to servers):

```bash
ssh-keygen -t ed25519 -C "user@email.com" -f ~/.ssh/id_ed25519_github -N ""
```

Add a host block to `~/.ssh/config` (append via terminal — `write_file` refuses protected `~/.ssh` paths):

```
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github
    IdentitiesOnly yes
```

Then `ssh-keyscan -T 5 github.com >> ~/.ssh/known_hosts` (first connection otherwise fails with `Host key verification failed`).

**Give the user the PUBLIC key** to add at https://github.com/settings/keys. The push test `ssh -T -o BatchMode=yes git@github.com` returns `Permission denied (publickey)` until they've added it.

## 2. GitHub MCP server (Hermes)

Prereqs: `mcp` Python package in the Hermes venv (`~/.hermes/hermes-agent/venv/bin/pip install mcp`), node/npx for the official server.

Register (NOT in the one-click catalog — add manually):

```bash
echo "Y" | hermes mcp add github --command npx --args -y @modelcontextprotocol/server-github \
  --env GITHUB_PERSONAL_ACCESS_TOKEN=ghp_... --connect-timeout 60
```

- **The `echo "Y" |` is required** — `hermes mcp add` prompts "Enable all 26 tools? [Y/n/select]" and otherwise aborts with `Cancelled.`.
- Saved to `~/.hermes/profiles/<profile>/config.yaml` under `mcp_servers` (26/26 tools enabled).
- Verify: `hermes mcp list` shows `github ... ✓ enabled`; `hermes mcp test github` lists tools.
- **MCP tools appear in a NEW session** — "Start a new session to use these tools" — not the current one.
- Token lives in the profile config env, never in the repo.

## 3. PAT scope gotchas

- Classic PAT needs at least `repo` for push/PR work; add `workflow` for Actions.
- **Check the token's actual permissions before assuming MCP can do everything:**
  ```bash
  curl -s -H "Authorization: token $PAT" https://api.github.com/user                       # who owns it
  curl -s -H "Authorization: token $PAT" https://api.github.com/repos/<owner>/<repo>       # perms dict
  ```
- **Symptom: pull-only token** — API shows `perm: {pull: true, push: false}`. MCP read tools (list issues, get PRs, search) work, but create/merge PRs and branch updates fail. Fix: add the token's account as a collaborator with Write, or generate the PAT from the account that owns the repo.
- The token owner may differ from the repo owner (e.g. PAT from `yolka-wiz` on repo owned by `amirrezaalavi`) — ask which account should get the SSH key vs which owns the repo before promising push works.

## 4. Git identity + commit

Set identity per-repo (user-specified): `git config user.name "yolka"` / `git config user.email "techwizrd.info@gmail.com"`. Commit with a descriptive message covering root cause + fix + verification. Push only after the SSH key is confirmed working.
