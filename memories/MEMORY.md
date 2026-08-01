SOCKS5 proxy at 127.0.0.1:10808 for web research.
§
Cisco IOS 12.2 RSA key gen needs 'general-keys' kw. OpenSSH 10.3 removed diffie-hellman-group1-sha1 — use 2048-bit key.
§
User wants all infrastructure/architecture plans to include a self-critique section reviewed through a cloud engineer's lens — call out SPOFs, bad architectural fits, missing backups, version drift risks, bootstrapping problems, and complexity vs value. Use a severity table format.
§
Hermes Agent 'yolka' @ 192.168.13.18 (Deb13, agent@, sudo). Hermes v0.19.0
§
FortiGate FG100D @ 192.168.4.4 (FW v6.2.17), user a.alavi / F0rti8orn@. MGMT firewall group needs core-srv added.
§
ESXi 6.7U3 @ 192.168.2.10, 127.7 GB RAM, VMs heavily overprovisioned (only 7.5% utilization). User alavi / ESX!8orn@.
§
VLANs: FLOOR3=192.168.13.0/24 (.1 Cisco sw, .4 FortiGate, .18 Agent). LAN4=192.168.4.0/24 (.40 WinSrv, .41 WinSrv, .60 Parghar-app, .100 FileSrv, .101-108 IP phones, .110/114 Cams, .120 core-srv, .200 printer, .254 gw). MGMT=192.168.2.0 firewalled. K3s+Incus on core-srv.
§
Credentials: a.csv (pipe-delimited) at C:\Users\netcon\Documents\. WinRM: template/Aa@123456@.43, admin/!@#123qwe@(.55 .58 .61 .62 .121). Veeam rescue/!@#123qwe@.11. File-srv admin/Aa@123456@.100.
§
OpenBao v2.6.1 Docker on core-srv :8200. Root token: s.l5pNqhyBU3WJQXn2Pkue432f. Engines: secret/, pki/, ssh/, transit/. Unseal keys /opt/bao/creds/.
§
WANs 10700-10702, src /opt/viberoxy. 8082 mirror & 30000 dashboard down.
§
Agent is its own GitHub user yolka-wiz (id 311797743): fork→push→PR workflow, dedicated GitHub SSH key registered with GH, fork remote at git@github.com:yolka-wiz/. GitHub MCP server registered (tools need new session). PAT in devops profile mcp config.
§
Identity backup: private repo yolka-wiz/yolka (checkout /home/agent/yolka-identity). build-identity.sh refreshes snapshot from profile; restore.sh reincarnates on new server. GitHub PAT deliberately redacted → placeholder in repo.