# FortiGate CLI Automation via expect

When the FortiGate REST API's write endpoints (`/api/v2/cmdb/`) return HTTP 403 or time out while read endpoints (`/api/v2/monitor/`) work fine, the admin user's API session has read-only scope. Use SSH + `expect` for write operations.

## Prerequisites

```bash
sudo apt-get install -y expect
```

## Pattern: Get a Session

```expect
#!/usr/bin/expect -f
set timeout 15
spawn ssh -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null \
  <user>@<fortigate-ip>
expect "password:"
send "<password>\r"
expect "$"    # FortiGate prompt ends with "$" or "#"
```

The prompt format is `FortiRad $` or `FortiRad (config-context) $`.

## Pattern: Add SSH Public Key to Admin User

```expect
#!/usr/bin/expect -f
set timeout 15
set key "<ssh-public-key-string>"
spawn ssh -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null \
  <user>@<fortigate-ip>
expect "password:"
send "<password>\r"
expect "$"
send "config system admin\r"
expect "$"
send "edit <admin-username>\r"
expect -re {\([^)]+\) \$}   # matches "FortiRad (username) $"
send "set ssh-public-key1 \"$key\"\r"
expect -re {\([^)]+\) \$}
send "end\r"
expect "$"
send "exit\r"
expect eof
```

## Pattern: Create Address Object

```expect
#!/usr/bin/expect -f
set timeout 15
spawn ssh -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null \
  <user>@<fortigate-ip>
expect "password:"
send "<password>\r"
expect "$"
send "config firewall address\r"
expect "$"
send "edit <object-name>\r"
expect -re {\([^)]+\) \$}
send "set subnet <ip> <netmask>\r"
expect -re {\([^)]+\) \$}
send "set type ipmask\r"
expect -re {\([^)]+\) \$}
send "end\r"
expect "$"
send "exit\r"
expect eof
```

## Pattern: Update Address Group Members

```expect
send "config firewall addrgrp\r"
expect "$"
send "edit <group-name>\r"
expect -re {\([^)]+\) \$}
send "set member <member1> <member2> ... <memberN>\r"
expect -re {\([^)]+\) \$}
send "end\r"
```

Note: `set member` replaces the entire member list. To append without removing existing members, collect the current list first with `show` before editing.

## Pattern: Verify Configuration

```expect
# From config context:
send "show\r"
expect -re {\([^)]+\) \$}

# From top-level:
send "show firewall addrgrp MGMT | grep -A5 \"member\"\r"
expect "$"
```

## Context-Specific Prompt Matching

FortiGate changes its prompt to indicate the current config context:
- `FortiRad $` — top-level
- `FortiRad (admin) $` — config system admin
- `FortiRad (a.alavi) $` — editing admin user a.alavi
- `FortiRad (address) $` — config firewall address
- `FortiRad (addrgrp) $` — config firewall addrgrp

Use `-re {\([^)]+\) \$}` as a generic match for any config-mode prompt.

## Known Working Pattern (FG100D v6.2.17)

The `edit` command enters the config context for the specified object. The prompt changes to `(object-name) $` or stays at `(config-section) $` depending on the FortiOS version. Always use `-re` for the prompt match to handle both patterns.
