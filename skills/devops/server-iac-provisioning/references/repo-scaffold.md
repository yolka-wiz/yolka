# Repo Scaffold Reference

Complete file listing and key content for the `infra/` IaC repo.

## File Tree

```
infra/
├── .gitignore
├── .env                         # 🔴 NOT committed — credentials
├── README.md
├── AGENT.md                     # AI agent instructions
├── docs/
│   └── architecture.md
├── ansible/
│   ├── ansible.cfg
│   ├── inventory.yml
│   ├── group_vars/all.yml
│   ├── playbooks/site.yml
│   └── roles/
│       ├── base/
│       │   ├── defaults/main.yml
│       │   ├── handlers/main.yml
│       │   └── tasks/main.yml
│       ├── firewall/
│       │   ├── defaults/main.yml
│       │   ├── handlers/main.yml
│       │   ├── tasks/main.yml
│       │   └── templates/nftables.conf.j2
│       ├── storage/
│       │   ├── defaults/main.yml
│       │   └── tasks/main.yml
│       ├── incus/
│       │   ├── defaults/main.yml
│       │   └── tasks/main.yml
│       ├── ctrld/
│       │   ├── defaults/main.yml
│       │   ├── handlers/main.yml
│       │   ├── tasks/main.yml
│       │   └── templates/ctrld.toml.j2
│       └── k3s/
│           ├── defaults/main.yml
│           └── tasks/main.yml
├── tofu/
│   ├── incus/
│   │   ├── providers.tf
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── cloud-init/
│   │       ├── samba.yml
│   │       └── ntp.yml
│   └── kubernetes/
│       ├── providers.tf
│       ├── main.tf
│       ├── variables.tf
│       └── values/
│           ├── kube-prometheus-stack.yaml
│           └── step-ca.yaml
└── scripts/
    ├── bootstrap.sh
    └── apply-all.sh
```

## Key File Contents

### ansible/group_vars/all.yml

```yaml
server_ip: 192.168.4.109
lan_cidr: 192.168.4.0/24
server_iface: eth0

static_drive_uuid: "CHANGE-ME"           # lsblk -o NAME,UUID
static_mount_point: /media/STATIC
static_fs_type: ext4

k3s_version: v1.31.2+k3s1
k3s_cluster_cidr: 10.42.0.0/16
k3s_service_cidr: 10.43.0.0/16
k3s_disable_traefik: false
k3s_write_kubeconfig_mode: "0644"
```

### ansible/inventory.yml

```yaml
all:
  hosts:
    core:
      ansible_host: 192.168.4.109
      ansible_user: core
      ansible_become: yes             # NOPASSWD sudo configured
      ansible_become_method: sudo
```

### ansible/ansible.cfg

```ini
[defaults]
inventory = inventory.yml
host_key_checking = False
retry_files_enabled = False
interpreter_python = auto_silent
gathering = smart
fact_caching_timeout = 3600
roles_path = /home/agent/playground/deploy/ansible/roles   # ABSOLUTE path

[ssh_connection]
pipelining = True
```

Note: `stdout_callback = yaml` was removed in ansible-core 2.21. If you want YAML output, add `result_format = yaml` to `[defaults]` instead.

### .env (sensitive, not in git)

```
CORE_SERVER_IP=192.168.4.109
CORE_SERVER_USER=core
CORE_SERVER_LAN_CIDR=192.168.4.0/24
CORE_SSH_KEY=~/.ssh/id_ed25519
K3S_VERSION=v1.31.2+k3s1
K3S_CLUSTER_CIDR=10.42.0.0/16
K3S_SERVICE_CIDR=10.43.0.0/16
```

### AGENT.md (AI agent instructions)

```
# AGENT.md
## Quick commands
  source .env && bash scripts/apply-all.sh
  kubectl get pods -A
  incus list
## One-time prep
  (format drive, set UUID, change passwords)
## Important passwords — file locations
## Backup paths
```

### ansible/playbooks/site.yml — Master playbook

```yaml
---
- name: Bootstrap Core-Services Server
  hosts: core
  become: yes
  pre_tasks:
    - name: Detect Debian codename
      shell: . /etc/os-release && echo "$VERSION_CODENAME"
      register: _codename
    - name: Set debian_codename fact
      set_fact: debian_codename="{{ _codename.stdout | trim }}"
  roles:
    - base
    - firewall
    - storage
    - incus
    - ctrld
    - k3s
```

### ansible/roles/storage/tasks/main.yml — External drive mount

Key pattern: mount by UUID, not /dev/sdX. Use `when:` to skip, not `end_play`:

```yaml
- name: Noop when UUID not set
  debug:
    msg: "UUID not set — skipping"
  when: static_drive_uuid == "PLACEHOLDER"

- name: Add to /etc/fstab
  ansible.builtin.mount:
    path: "{{ static_mount_point }}"
    src: "UUID={{ static_drive_uuid }}"
    fstype: "{{ static_fs_type }}"
    opts: defaults,noatime
    state: mounted
  when: static_drive_uuid != "PLACEHOLDER"
```

### ansible/roles/ctrld/tasks/main.yml — Download from GitHub API

ctrld now ships as a versioned .tar.gz, not a standalone binary:

```yaml
- name: Get latest version from GitHub API
  ansible.builtin.uri:
    url: https://api.github.com/repos/Control-D-Inc/ctrld/releases/latest
    return_content: yes
  register: _gh_release

- name: Set version fact
  set_fact:
    ctrld_version: "{{ _gh_release.json.tag_name | replace('v', '') }}"

- name: Download tar.gz
  ansible.builtin.get_url:
    url: "https://github.com/Control-D-Inc/ctrld/releases/download/v{{ ctrld_version }}/ctrld_{{ ctrld_version }}_linux_{{ ctrld_arch }}.tar.gz"
    dest: "/tmp/ctrld_tarball.tar.gz"

- name: Extract binary
  ansible.builtin.unarchive:
    src: "/tmp/ctrld_tarball.tar.gz"
    dest: /usr/local/bin/
    remote_src: yes
    include: ctrld
    mode: "0755"
```

### ansible/roles/k3s/tasks/main.yml — k3s install

```yaml
- name: Install k3s
  ansible.builtin.command: >
    /tmp/k3s-install.sh
    --write-kubeconfig-mode {{ k3s_write_kubeconfig_mode }}
    --cluster-cidr {{ k3s_cluster_cidr }}
    --service-cidr {{ k3s_service_cidr }}
  environment:
    INSTALL_K3S_VERSION: "{{ k3s_version }}"

- name: Wait for k3s API
  command: k3s kubectl get nodes
  register: _api
  until: _api.rc == 0
  retries: 30
  delay: 5
  changed_when: false
```

### tofu/incus/main.tf — Incus containers with proxy + disk devices

```
resource "incus_container" "samba" {
  name      = "samba"
  image     = "images:debian/12/cloud"
  config = { "user.user-data" = file("cloud-init/samba.yml") }

  device { name="smb-445"; type="proxy"
    properties = { listen="tcp:192.168.4.109:445", connect="tcp:127.0.0.1:445" }
  }
  device { name="samba-disk"; type="disk"
    properties = { source="/media/STATIC/samba/public", path="/srv/samba/public" }
  }
}
```

### tofu/kubernetes/main.tf — Helm releases + manual PVs

```hcl
resource "helm_release" "kube_prometheus" {
  name       = "kube-prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "69.2.0"   # pin version — never float
  values     = [file("values/kube-prometheus-stack.yaml")]
}

resource "helm_release" "step_ca" {
  name       = "step-ca"
  repository = "https://smallstep.github.io/helm-charts"
  chart      = "step-certificates"
  namespace  = "ca"
  version    = "1.26.0"
  values     = [file("values/step-ca.yaml")]
}
```

## Critical Security Notes

1. **All default passwords** (Grafana, step-ca admin, Samba core user) are in plaintext in values/cloud-init files. They MUST be changed after first deploy.
2. **step-ca root key** lives in a PVC on `/media/STATIC/containers/ca/`. This directory must be backed up off-server.
3. **k3s kubeconfig** at `/etc/rancher/k3s/k3s.yaml` grants full cluster admin. Restrict file permissions.
4. **Firewall is LAN-only** — no WAN exposure. All ports restricted to `lan_cidr`.

## Post-Deploy Must-Do

- [ ] Copy kubeconfig off-server
- [ ] Change Grafana admin password (default: `changeme`)
- [ ] Change step-ca provisioner password (default: `changeme`)
- [ ] Change Samba core user password (default: `changeme`)
- [ ] Run `kubectl exec -n ca deploy/step-ca -- step ca init`
- [ ] Point LAN client DNS to server IP (:53)
- [ ] Verify: `incus list`, `kubectl get pods -A`, `kubectl get svc -n monitoring`
