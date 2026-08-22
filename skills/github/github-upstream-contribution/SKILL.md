---
name: github-upstream-contribution
description: Fork upstream GitHub repositories when push is unavailable.
version: 1.0.0
author: yolka
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, permissions, forks, issues, pull-requests, security]
    related_skills: [github-auth, github-issues, github-pr-workflow, github-repo-management]
---

# Upstream GitHub Contribution Workflow

Use this skill when the authenticated account can read an upstream repository but may not be able to push directly. The core rule is: **successful clone/fetch is not evidence of write access**. Verify permissions first, then choose direct push or fork-based contribution.

## When to Use

Use when a GitHub repository can be cloned or queried but direct upstream push access is uncertain or unavailable, especially when issues can be created but code must go through a fork and cross-repository PR.

## 1. Verify access before mutating anything

Run these read-only checks:

```bash
gh auth status
gh api repos/OWNER/REPO --jq '{full_name,permissions,default_branch,has_issues}'
git remote -v
git ls-remote origin HEAD
```

Record:

- authenticated login
- upstream owner/repository
- default branch
- `permissions.push`, `permissions.maintain`, and `permissions.admin`
- whether issues are enabled
- whether CI checks are configured

Do not ask for a new token when the existing API identity already works. If issue creation works but upstream push is denied, use the fork path.

## 2. Order security and maintenance work

For a source audit or security review:

1. Create one issue per independently actionable finding, with exact file/line evidence, impact, preconditions, and remediation.
2. Verify each issue URL and state immediately.
3. Create a focused branch for one coherent fix or documentation deliverable.
4. Open a PR that references the issue.
5. Use `Related to #N` or `Partially addresses #N` for incomplete mitigation. Use `Closes #N` only when the PR fully resolves the issue.
6. Verify the PR's head branch, base branch, state, body, and checks.

Keep audit documentation separate from code changes unless the user explicitly asks for a combined PR.

## 3. Fork fallback when upstream push is unavailable

```bash
# Create or reuse the fork
gh repo fork OWNER/REPO --remote=false

# Add and fetch the fork
git remote add fork https://github.com/ME/REPO.git
git fetch fork

# Base work on the fork's current default branch
git switch -c fix/short-description fork/DEFAULT_BRANCH

# Make and verify changes
git diff --check
git add <specific-files>
git commit -m "fix: short description"
git push -u fork HEAD

# Open a cross-repository PR
gh pr create \
  --repo OWNER/REPO \
  --head ME:BRANCH \
  --base DEFAULT_BRANCH \
  --title "fix: short description" \
  --body-file /tmp/pr-body.md
```

Do not use the upstream `origin` for push commands when its permission is read-only. Keep `origin` pointing at upstream and `fork` pointing at the writable fork so review diffs remain clear.

## 4. Verify every external side effect

Read back the actual GitHub objects; never rely only on CLI success text:

```bash
gh issue view ISSUE --repo OWNER/REPO --json number,state,title,url

gh pr view PR --repo OWNER/REPO \
  --json number,state,title,url,headRefName,baseRefName,body

gh pr checks PR --repo OWNER/REPO
```

`gh pr checks` returning “no checks reported” is a verified state, not a successful CI result. Report it as no configured/reported checks.

## 5. Body hygiene and security review content

Issue and PR bodies are external side effects. Before publishing them:

- remove credentials, tokens, private hostnames, and unnecessary internal paths
- scan for invisible Unicode/zero-width characters
- avoid `curl | bash` examples unless explicitly describing the vulnerability
- do not claim a partial fix closes a broad issue
- use a temporary body file and read back the published body if exact text matters

A robust update path for a body that did not round-trip correctly through `gh pr edit` is:

```bash
python3 - <<'PY'
import json
body = open('/tmp/pr-body.md', encoding='utf-8').read()
open('/tmp/pr-patch.json', 'w', encoding='utf-8').write(json.dumps({'body': body}))
PY
gh api --method PATCH repos/OWNER/REPO/issues/PR --input /tmp/pr-patch.json
```

## 6. Evidence and scope discipline

Security findings must distinguish:

- verified source behavior
- locally exercised behavior
- claims that lack tests or benchmarks
- hypotheses requiring deployed-environment validation

Do not install remote scripts or alter production systems as part of a repository review. Build, lint, unit, race, protocol smoke, and static checks are acceptable when run locally.

## References

- `references/permission-fallback.md` — concise command sequence and failure-mode checklist for issue → fork branch → upstream PR workflows.
