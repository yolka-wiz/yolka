# FortiGate SMB Inspection — Full Diagnostic Reference

## Symptom Checklist

| Test | Expected | Actual (broken) |
|------|----------|-----------------|
| `ping 192.168.4.100` | Reply <5ms | ✅ Same |
| `Test-NetConnection -Port 445 192.168.4.100` | TcpTestSucceeded: True | ✅ True |
| `net view \\192.168.4.100` | List of shares | ❌ Error 1702: The binding handle is invalid |
| `net use X: \\192.168.4.100\Software` | Command completed | ❌ Error 67: The network name cannot be found |
| `dir \\192.168.4.100\Software` | File listing | ❌ The system cannot find the file specified |
| Raw TCP: connect + send bytes | Connection then reset | ❌ Timeout or RST |

## Root Cause Chain

1. FortiGate has **SMB inspection** enabled on the internal zone policy
2. The firewall intercepts TCP/445 and proxies the SMB session
3. For modern SMB dialects (SMB 3.x with encryption), the proxy fails to negotiate
4. NetBIOS session setup (part of SMB) fails → RPC binding handle is invalid
5. `net use` falls back to attempting name resolution → "network name not found"

## Server-Side Detection (run on the file server)

```powershell
# Check port 445 listener and active connections
netstat -ano | findstr :445

# Expected output (direct SMB, no proxy):
# TCP    0.0.0.0:445            0.0.0.0:0              LISTENING
# TCP    192.168.4.100:445      192.168.4.126:xxxxx     ESTABLISHED  ← client IP

# Broken output (FortiGate proxy):
# TCP    0.0.0.0:445            0.0.0.0:0              LISTENING
# TCP    192.168.4.100:445      192.168.4.4:xxxxx      ESTABLISHED  ← ALL from gateway!
# TCP    192.168.4.100:445      192.168.4.4:xxxxx      ESTABLISHED
# TCP    192.168.4.100:445      192.168.4.4:xxxxx      ESTABLISHED  ← 15+ connections
```

## Client-Side Detection

```powershell
# Check SMB server config
Get-SmbServerConfiguration | Select-Object EnableSMB2Protocol, RejectUnencryptedAccess, EnableStrictNameChecking

# Test raw TCP (not enough — TCP works but SMB negotiation fails)
Test-NetConnection -ComputerName 192.168.4.100 -Port 445

# Test SMB protocol specifically
net view \\192.168.4.100   # Error 1702 = SMB proxy issue
```

## Permanent Resolution (FortiGate CLI)

```bash
# Option 1: Create a dedicated inter-VLAN policy without SMB inspection
config firewall policy
    edit <new-id>
        set name "Internal-No-Inspection"
        set srcintf "internal"
        set dstintf "internal"
        set srcaddr "lan_subnet"
        set dstaddr "lan_subnet"
        set action accept
        set schedule "always"
        set service "ALL"
        set inspection-mode flow        # flow mode = no proxy
        set utm-status disable
        set av-profile ""
        set ips-sensor ""
        set application-list ""
    next
end

# Option 2: Disable inspection on existing policy
config firewall policy
    edit <existing-policy-id>
        set inspection-mode flow
        set utm-status disable
    next
end
```

## Why It Matters for Software Deployment

When installing software via WinRM across FortiGate-inspected subnets:
- You CANNOT rely on `\\server\share` to transfer installer files
- WinRM (port 5985) is NOT affected — management connectivity is fine
- The HTTP workaround is the only reliable transfer method
- Check SMB early in the workflow so you don't waste time debugging "permissions" or "credentials"
