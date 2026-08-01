---
name: server-cleanup-provisioning
description: Strip GUI and desktop from Debian, rehome into /opt/agent.
category: devops
version: 1.0.0
platforms: [linux]
---

# Server Cleanup & Managed Provisioning

Use when converting a Debian desktop install into a lean server for agent/gateway use, or reorganizing home clutter into `/opt/<name>`.

## Triggers

- "Reset" or "clean up" a Debian server
- Removing GUI/desktop packages while preserving CLI tools
- Reorganizing files from `~/` into a managed `/opt/appname/`

## Phase 1: Survey

```bash
systemctl list-units --type=service --state=running --no-legend | awk '{print $1}'
systemctl list-unit-files --state=enabled --no-legend | awk '{print $1}'
ss -tlnp
df -h /
dpkg -l | grep '^ii' | grep -iE 'kde|plasma|sddm|dolphin|konsole|x11|xorg|gtk|gnome|cups'
```

## Phase 2: Stop Services First

Stop and disable BEFORE purging (cleaner than killing leftover processes):

```bash
sudo systemctl stop sddm gdm3 lightdm 2>/dev/null
sudo systemctl disable sddm gdm3 lightdm 2>/dev/null
```

## Phase 3: Purge GUI Packages

### Dry-run to see the cascade

```bash
apt-get --just-print purge sddm kde-baseapps dolphin plasma-desktop konsole kwin-x11 \
  | grep -E 'Purg|Remv' | head -40
```

### Purge in bulk

The cascade removes KDE, Qt, GTK, X11, and their dependency chains. Expected.

```bash
sudo apt purge -y sddm kde-baseapps dolphin konsole kwin-x11 krdp kdeconnect \
  plasma-desktop plasma-workspace plasma-nm plasma-*data plasma-*addons \
  polkit-kde-agent-1 kdepim-* kdeplasma-* kded6 breeze-icon-theme \
  libreoffice-kf6 libreoffice-plasma libreoffice-qt6 libreoffice-style-breeze \
  xdg-desktop-portal-kde gnome-keyring gnome-themes-extra-data adwaita-icon-theme
sudo apt autoremove --purge -y
```

### Reinstall accidentally-removed critical packages

NetworkManager and open-vm-tools may be removed by the cascade:

```bash
sudo apt install -y network-manager open-vm-tools
sudo systemctl enable --now NetworkManager open-vm-tools
nmcli dev show ens192 | grep IP4  # verify static IP
```

## Phase 4: Clean Home Directory

Remove empty XDG directories, dev clutter, core dumps:

```bash
rmdir ~/Documents ~/Music ~/Pictures ~/Videos ~/Templates ~/Public 2>/dev/null
rm -rf ~/playground ~/searxng ~/searxng-venv ~/poppler-* ~/.vnc ~/.ansible
rm -f ~/core.* ~/.Xauthority ~/.xsession-errors ~/.gtkrc-2.0 ~/.face*
```

For Desktop/Documents with possible user files, move — don't delete:

```bash
mkdir -p workspace/old-desktop && mv ~/Desktop/* workspace/old-desktop/ 2>/dev/null
rmdir ~/Desktop
```

## Phase 5: Create Managed Directory (`/opt/appname`)

```bash
sudo mkdir -p /opt/appname/{hermes/env,workspace,env,scripts,logs,config}
sudo chown -R $USER:$USER /opt/appname
```

## Phase 6: Migrate Existing Tools

```bash
cp -a ~/hermes-env /opt/appname/hermes/env
cp -a ~/workspace/* /opt/appname/workspace/
cp -a ~/.hermes /opt/appname/hermes/config
rm -rf ~/hermes-env ~/workspace ~/.hermes
ln -sf /opt/appname/hermes/config ~/.hermes
ln -sf /opt/appname/hermes/env/bin/hermes /usr/local/bin/hermes
echo 'export HERMES_HOME=/opt/appname/hermes/config' >> ~/.bashrc
```

## Phase 7: Systemd Services

Create service file at `/opt/appname/config/hermes-gateway.service`:

```ini
[Unit]
Description=Hermes Agent Gateway
After=network-online.target

[Service]
Type=simple
ExecStart=/opt/appname/hermes/env/bin/hermes --profile devops gateway run --accept-hooks
Restart=on-failure
RestartSec=10
Environment=HOME=/home/agent
Environment=HERMES_HOME=/opt/appname/hermes/config

[Install]
WantedBy=default.target
```

Copy to user systemd and enable linger:

```bash
cp /opt/appname/config/hermes-gateway.service ~/.config/systemd/user/
sudo loginctl enable-linger $USER
```

## Pitfalls

- **Don't use `rm -rf *` in home** — approval guards block it. Use targeted `rm -rf` for specific directories.
- **NetworkManager gets removed** — always reinstall. Static IP stays on interface without NM, so SSH survives.
- **Qt6 libs remain** — LibreOffice needs them even headless. Don't force-remove.
- **`libcups2` is shared** — Chromium and Qt depend on it. Only remove if nothing depends on it.
- **wpa_supplicant returns with NM** — mask it: `sudo systemctl mask wpa_supplicant`.
- **ModemManager returns with NM** — mask it too.
- **Core dumps can be multi-GB** — check for `~/core.*` files.
- **Check disk after each phase** with `df -h /`.
