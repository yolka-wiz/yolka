# FortiGate REST API Access

## Authentication

FortiOS (tested on v6.2.17, FG100D) uses **form-based login** to obtain a session cookie — there is no API token in this version.

```bash
# 1. POST credentials to /logincheck
CSRF=$(curl -sk -c /tmp/fg-cookies -b /tmp/fg-cookies \
  -d "username=admin&secretkey=password" \
  "https://<fortigate-ip>/logincheck" 2>&1)

# 2. Use the cookie for subsequent API calls
curl -sk -b /tmp/fg-cookies \
  "https://<fortigate-ip>/api/v2/monitor/system/status"
```

The login response is a JavaScript redirect to `/ng/prompt?redir=%2Fng` — this is expected and not an error. The session cookie is set regardless.

## Useful API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/api/v2/monitor/system/status` | Device info: model, serial, firmware version, HA status |
| `/api/v2/monitor/system/dhcp` | DHCP lease table (IP, MAC, hostname, interface, VCI, reserved status) |
| `/api/v2/monitor/system/interface` | Interface list with IPs, VLANs, status |
| `/api/v2/monitor/firewall/policy` | Firewall policy listing |
| `/api/v2/monitor/router/static` | Static routes |
| `/api/v2/monitor/system/admin` | Admin users |
| `/api/v2/monitor/vpn/ipsec` | IPsec tunnel status |

## DHCP Lease Response Shape

```json
{
  "results": [
    {
      "ip": "192.168.x.x",
      "mac": "aa:bb:cc:dd:ee:ff",
      "hostname": "DESKTOP-XXXXXXX",
      "vci": "MSFT 5.0",
      "interface": "VLAN-NAME",
      "reserved": false,
      "expire_time": 1784556023,
      "status": "leased",
      "type": "ipv4"
    }
  ]
}
```

Key fields:
- **`vci`** — Vendor Class Identifier: `"MSFT 5.0"` = Windows DHCP client, `"yealink"` = VoIP phone, `"ubnt"` = Ubiquiti AP, `"android-dhcp-*"` = Android device, `"udhcp 1.26.2"` = embedded Linux
- **`interface`** — The VLAN/interface name in FortiGate config
- **`reserved`** — Whether this is a DHCP reservation (static mapping)

## VLAN Discovery via DHCP

When you need to find all Windows computers on a network but lack credentials for each one, query the FortiGate DHCP lease table. The `interface` field tells you which VLAN each device is on.

## Limitations

- **No API key/secret in v6.2.x** — cookie-based auth only; cookies expire
- **API endpoints are read-only in monitor namespace** — changes require different endpoints
- **Rate limiting** — the FortiGate management CPU is shared; don't hammer the API
- **Multi-VDOM** — if the device has multiple VDOMs, you may need to specify `?vdom=root` in the URL
