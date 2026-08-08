# RESTORE — compact agent guide (yolka profile)

Hand this to the agent on the NEW server. It can do everything itself.
Private repo: `yolka-wiz/yolka` · Branch: `2026-08-08` · Passphrase: given by user.

## 1. Get the profile

```bash
git clone git@github.com:yolka-wiz/yolka.git && cd yolka
git checkout 2026-08-08
# install Hermes at the version in VERSION, then:
hermes --version   # must match VERSION (version drift breaks profile)
```

## 2. Install profile files

```bash
P=~/.hermes/profiles/yolka && mkdir -p "$P"/{memories,skills,cron}
cp SOUL.md "$P/"
cp memories/MEMORY.md memories/USER.md "$P/memories/"
cp -r skills/. "$P/skills/"
cp -r cron/. "$P/cron/"
cp config.yaml "$P/"        # already redacted
```

## 3. Decrypt secrets (ONCE, then delete plaintext)

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -salt \
  -in secrets.enc -out /tmp/secrets.yaml    # passphrase from user
# apply: OPENCODE_GO_API_KEY -> "$P/.env"
#        gh PAT               -> ~/.config/gh/hosts.yml (chmod 600) + `gh auth status`
#        SSH key bodies       -> ~/.ssh/ (chmod 600) + ~/.ssh/config
rm -f /tmp/secrets.yaml
```

## 4. Verify

```bash
hermes --version                     # matches VERSION
gh auth status                       # yolka-wiz
ssh -T git@github.com                # auth via id_ed25519_github
hermes config get mcp_servers.context7   # placeholder — real key from user if needed
# start a session → you should be yolka with 48 skills + memories
```

## Rules for the agent

- Never commit: `/tmp/secrets.yaml`, `.env`, `hosts.yml`, private keys.
- If any step fails (version mismatch, key not accepted): STOP and report — don't improvise.
- After restore, offer to rotate the GitHub PAT (user decides).
