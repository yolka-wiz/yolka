# Permission Fallback Checklist

Use this after cloning an upstream repository when the next action may write GitHub state.

## Read-only access check

```bash
gh auth status
gh api repos/OWNER/REPO --jq '{full_name,permissions,default_branch,has_issues}'
git remote -v
git ls-remote origin HEAD
```

Interpretation:

- clone/fetch succeeds: read access only is proven
- `permissions.push=true`: direct branch push may be possible
- `permissions.push=false` and issues enabled: create issues upstream, then use a fork
- no API identity: stop before creating issues, forks, or PRs and request authentication

## Fork-to-PR sequence

```bash
gh repo fork OWNER/REPO --remote=false
git remote add fork https://github.com/ME/REPO.git
git fetch fork
git switch -c fix/short-description fork/DEFAULT_BRANCH
git diff --check
git add <specific-files>
git commit -m "fix: short description"
git push -u fork HEAD
gh pr create --repo OWNER/REPO --head ME:BRANCH --base DEFAULT_BRANCH --body-file /tmp/pr-body.md
```

## Verification checklist

```bash
gh issue view ISSUE --repo OWNER/REPO --json number,state,title,url
gh pr view PR --repo OWNER/REPO --json number,state,title,url,headRefName,baseRefName,body
gh pr checks PR --repo OWNER/REPO
```

Record “no checks reported” as an absent CI result, not a passing check. Use `Related to` or `Partially addresses` for incomplete fixes; reserve `Closes` for complete fixes. Scan published bodies for credentials and zero-width Unicode.
