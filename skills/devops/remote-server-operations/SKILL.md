---
name: remote-server-operations
description: Write files, deploy configs, transfer content, and manage Hermes profiles on remote servers via SSH — avoiding quoting pitfalls and verifying integrity.
category: devops
version: 1.0.0
---

# Remote Server Operations

Patterns for writing files, deploying configurations, and managing Hermes profiles on remote Linux servers via SSH. Covers the quoting pitfalls that silently corrupt content and the verification workflow that catches them.

## When to Use

- Writing config files, skill files, or scripts to a remote server via SSH
- Deploying Hermes profiles, SOUL.md, soul.json, and skills to a remote host
- Any SSH-based file transfer where content contains quotes, backslashes, or triple-quoted strings
- Setting up a new Hermes profile from scratch on a remote server

## The Core Rule

**Never inline complex content into SSH commands.** Shell quoting layers (local bash → SSH → remote bash → Python string) inevitably corrupt content with triple quotes, backslashes, or nested quotes. Use the two-step pattern instead.

## Proven Workflow: Write Locally, SCP

```bash
# Step 1: Write the file locally (handles all escaping correctly)
write_file(path="local-skill.md", content="...")

# Step 2: Transfer to remote — no shell interpretation
scp local-skill.md user@host:/remote/path/SKILL.md
```

This avoids every quoting issue because `write_file` writes bytes directly to disk, and `scp` transfers them as-is. No shell interpretation layer between your content and the destination file.

## The SSH Heredoc Trap (Anti-Pattern)

These patterns **will fail silently** when content contains triple-quoted strings, escaped backslashes, or nested quotes:

```bash
# FAILS: bash interprets escapes inside the heredoc
ssh remote 'python3' << 'PYEOF'
with open('/path/file', 'w') as f:
    f.write("""content with \"\"\" triple quotes""")
PYEOF

# FAILS: quoting nightmare with -c
ssh remote python3 -c "
with open('/path/file', 'w') as f:
    f.write('...')
"
```

**Symptoms when it fails:**
- Exit code 0, "file written" printed, but `wc -l` shows 39 lines instead of 200+
- `SyntaxError` from Python about mismatched quotes
- `unexpected EOF while looking for matching` from bash
- `Permission denied` on file creation (directory wasn't created)

## Always Verify After Remote Writes

After any remote file write, verify content integrity — don't trust exit codes:

```bash
# Check line count and byte size
ssh remote "wc -l /remote/path/file && wc -c /remote/path/file"

# For skill files, verify frontmatter and structure
ssh remote "head -5 /remote/path/file"

# For critical configs, check YAML parses
ssh remote "python3 -c 'import yaml; yaml.safe_load(open(\"/remote/path/config.yaml\"))' && echo OK"
```

If line counts are suspiciously low (e.g., 40 when you wrote 200+), the content was truncated. Re-transfer via `scp`.

## Hermes Profile Directory Structure

When creating a Hermes profile from scratch on a remote server, `hermes profile create NAME` makes directories but does NOT create `config.yaml` or the `soul/` directory. You need to create these manually:

```
~/.hermes/profiles/<name>/
├── config.yaml          ← MANUAL — write this yourself
├── SOUL.md              ← MANUAL — write this yourself
├── soul/
│   └── soul.json        ← MANUAL — mkdir -p soul/ first, then write
├── skills/
│   └── <skill-name>/
│       └── SKILL.md     ← MANUAL — mkdir -p skills/<name>/ first, then write
├── .env                 ← auto-created (empty template)
├── cron/                ← auto-created
├── logs/                ← auto-created
├── memories/            ← auto-created
├── plans/               ← auto-created
├── sessions/            ← auto-created
├── skins/               ← auto-created
├── home/                ← auto-created
└── workspace/           ← auto-created
```

**Key gotcha:** `soul/` and each `skills/<name>/` directory must be created with `mkdir -p` before writing files into them — the profile create command only makes the top-level profile directory and its auto-created children.

## Batch Deploy Multiple Files

When deploying multiple skill files or configs to a remote server, batch the `scp` calls:

```bash
scp local-file1.md user@host:/remote/path1/SKILL.md && \
scp local-file2.md user@host:/remote/path2/SKILL.md && \
scp local-file3.md user@host:/remote/path3/SKILL.md && \
echo "All files transferred"
```

Then verify all at once:

```bash
ssh remote "wc -l /remote/path1/SKILL.md /remote/path2/SKILL.md /remote/path3/SKILL.md"
```

## Double-Hop SSH: The Script-on-Jumpbox Pattern

When you need to run commands through **two SSH hops** (e.g., Hermes → jump box → target server), single-quote nesting breaks immediately:

```bash
# ❌ FAILS — single quotes in outer ssh close at the first inner single quote:
ssh agent@jumpbox 'ssh user@target '
command1
command2
''
```

**Working pattern:** Write the inner command as a script on the jump box, then execute it:

```bash
# ✅ WORKS — script on jump box, inner commands via bash heredoc:
ssh agent@jumpbox 'cat > /tmp/script.sh << "EOF"
ssh user@target bash << "INNER"
echo "=== COMMAND 1 ==="
sudo command1
echo "=== COMMAND 2 ==="
sudo command2
INNER
EOF
bash /tmp/script.sh'
```

This avoids all single-quote nesting because:
- The outer `ssh` command is in single quotes (no variable expansion)
- The script content uses a heredoc `<< "EOF"` that preserves everything literally
- The inner SSH uses a second heredoc `<< "INNER"` — quotes within quotes work because bash is writing the inner heredoc delimiter, not evaluating it

**Verify after double-hop** — a follow-up SSH command is more reliable than trusting the script's exit code:

```bash
ssh agent@jumpbox 'ssh user@target "cat /path/to/file | head -5"'
```

### Quick one-liner for short inner commands

```bash
ssh agent@jumpbox "echo 'ssh user@target \"ls -la /path\"' | sh"
```

But this breaks with complex quoting, so prefer the full script pattern above.

## Pitfalls

- **Trusting exit codes**: SSH may exit 0 even when the remote command silently truncated output. Always verify with `wc -l`.
- **Forgetting mkdir -p**: `scp` won't create intermediate directories. Create the full path first with `ssh remote 'mkdir -p /path/to/dir'`.
- **Windows path separators in scp**: Use forward slashes or quotes: `scp "C:/Users/name/file.md" user@host:/path/`.
- **Line ending corruption**: `scp` preserves line endings as-is. If you write files with `write_file` (Unix `\n`), they stay Unix on the remote.
- **Permission issues**: `scp` preserves local permissions. If the remote user can't write, pre-create the dir with `mkdir -p` and check ownership.

## Alternative: execute_code with Temporary Files

When `write_file` and `scp` aren't ideal (e.g., writing many files from within a code block), use Python's `tempfile` + `scp` from the `execute_code` sandbox:

```python
from hermes_tools import terminal, write_file
import tempfile

# Write content to temp file
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
    f.write(content)
    tmp = f.name

# SCP to remote — no shell interpretation of content
result = terminal(f'scp "{tmp}" user@host:/remote/path/file.md', timeout=10)
# Clean up
os.unlink(tmp)
```

This avoids all the SSH heredoc and quoting issues while keeping the code clean.

## References

- **Hermes Dashboard Basic Auth Fix**: See [references/hermes-dashboard-basic-auth-fix.md](references/hermes-dashboard-basic-auth-fix.md) — fixes the HTTP 500 error when binding the Hermes Dashboard to `0.0.0.0` with basic auth (password-based, no OAuth).
