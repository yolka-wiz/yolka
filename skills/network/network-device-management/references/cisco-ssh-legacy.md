# Cisco SSH Legacy Compatibility

Reference for troubleshooting and fixing SSH on old Cisco IOS switches (12.2/15.0) that only support deprecated algorithms.

## Algorithm Matrix (Catalyst 2960S / 3750E)

| IOS Version | KEX | Host Key | Ciphers | MACs |
|-------------|-----|----------|---------|------|
| 12.2(55)SE3 | diffie-hellman-group1-sha1 | ssh-rsa | aes128-cbc, 3des-cbc | hmac-sha1 |
| 15.0(2)SE11 | diffie-hellman-group1-sha1 | ssh-rsa | aes128-cbc, 3des-cbc | hmac-sha1 |
| 15.2(2)E9+ | diffie-hellman-group1-sha1 | ssh-rsa | aes128-ctr, aes192-ctr, aes256-ctr, aes128-cbc, 3des-cbc, aes192-cbc, aes256-cbc | hmac-sha1, hmac-sha1-96 |

Key finding: **No IOS version on these switches supports** modern KEX (curve25519, ecdh-nist, group14/16), host key algorithms (rsa-sha2-256/512, ed25519), or EtM MACs. The only path to SSH access is enabling legacy algorithms on the client OR regenerating the switch RSA key to 2048-bit.

## SSH Failure Diagnosis Flow

### Symptom 1: "no matching key exchange method found. Their offer: diffie-hellman-group1-sha1"

Client: OpenSSH 8.8+ removed group1 from defaults. OpenSSH 10.3+ removed it entirely — even `+diffie-hellman-group1-sha1` fails.

**Fix:** Regenerate RSA key on switch (see below). The "Invalid key length" error that follows the KEX failure is the real blocker.

### Symptom 2: "no matching host key type found. Their offer: ssh-rsa"

Client: OpenSSH 8.8+ deprecated ssh-rsa for host keys. OpenSSH 10.3 disabled it by default.

**Workaround:** `-oHostKeyAlgorithms=+ssh-rsa`

### Symptom 3: "no matching cipher found. Their offer: aes128-cbc,3des-cbc,..."

Client: OpenSSH removed CBC ciphers from defaults.

**Workaround:** `-oCiphers=+aes128-cbc`

### Symptom 4: "Invalid key length"

**Root cause:** Switch RSA host key is 512 or 768 bits. OpenSSH minimum is 1024 bits (RequiredRSASize default).

**Fix:** Regenerate with 2048-bit modulus via telnet.

## RSA Key Regeneration Commands

### Check current key
```
show crypto key mypubkey rsa
```

### Key generation syntax by IOS version

**IOS 12.2 (e.g. 12.2(55)SE3):**
```
conf t
crypto key generate rsa general-keys modulus 2048
```
Note: `general-keys` keyword is REQUIRED on 12.2. Without it, `modulus` is not recognized.

**IOS 15.x (e.g. 15.0(2)SE11, 15.2(2)E9):**
```
conf t
crypto key generate rsa modulus 2048
```

### Handling the replacement prompt

When a key already exists, the switch asks:
```
% You already have RSA keys defined named SW-F0.borna.
% They will be replaced.
Do you really want to replace them? [yes/no]:
```

Send: `yes`

### Key generation timing

- 2048-bit on 2960S/3750E: 20-90 seconds depending on CPU load
- IOS 12.2 is noticeably slower than 15.x
- During generation the switch is busy — don't interrupt

### After key generation
```
end
write memory
```

### If regeneration fails

1. Remove old key first, then generate fresh:
```
conf t
crypto key zeroize rsa <keyname>
```
2. Wait — SSH server stops accepting connections after zeroize
3. Generate fresh key with one of the commands above

### Verify new key
```
show ip ssh
show crypto key mypubkey rsa | include Key name
```

## Client-Side SSH Config for Post-Fix Access

Even with 2048-bit keys, the switches only offer legacy algorithms. Add this to `~/.ssh/config`:

```
Host 192.168.1.10? 192.168.1.110
    KexAlgorithms +diffie-hellman-group1-sha1
    HostKeyAlgorithms +ssh-rsa
    Ciphers +aes128-cbc
    MACs +hmac-sha1
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    PreferredAuthentications password
```

Or one-liner:
```bash
ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 \
    -oHostKeyAlgorithms=+ssh-rsa \
    -oCiphers=+aes128-cbc \
    -oMACs=+hmac-sha1 \
    a.alavi@192.168.1.100
```

## Encoded Key Size Heuristic

From `show crypto key mypubkey rsa`, the hex output encodes the RSA public key in DER.

| Hex prefix | Modulus length | Key bits |
|------------|---------------|----------|
| `307C300D...` | 0x61 = 97 bytes | ~768 |
| `30819F30...` | 0x81 = 129 bytes | ~1024 |
| `3082010A...` | 0x101 = 257 bytes | ~2048 |

The key hex starts right after `Key Data:` line. Count the hex digits in the first block for a rough estimate: ~86 hex chars = 768-bit, ~130 = 1024-bit, ~260 = 2048-bit.

## OpenSSH Version Compatibility

| OpenSSH Version | diffie-hellman-group1-sha1 | ssh-rsa (host key) | CBC ciphers |
|----------------|---------------------------|-------------------|-------------|
| < 7.0 | Supported by default | Supported by default | Supported |
| 7.0-8.7 | Supported by default | Supported | Supported |
| 8.8-9.9 | Disabled (+ works) | Disabled (+ works) | Disabled (+ works) |
| 10.0-10.3+ | **Removed entirely** | Disabled (+ works) | Disabled (+ works) |

**Paramiko 5.0:** Removed `kex_group1` module entirely. Cannot connect to any device that only offers diffie-hellman-group1-sha1.

## Summary Commands

```bash
# Check if SSH works
ssh -o StrictHostKeyChecking=no \
    -oKexAlgorithms=+diffie-hellman-group1-sha1 \
    -oHostKeyAlgorithms=+ssh-rsa \
    -oCiphers=+aes128-cbc \
    -oMACs=+hmac-sha1 \
    a.alavi@<switch-ip> "show ip ssh | include SSH"

# Key size check (via telnet)
show crypto key mypubkey rsa

# Permanent fix (via telnet)
conf t
crypto key generate rsa general-keys modulus 2048   # IOS 12.2
crypto key generate rsa modulus 2048                # IOS 15.x
end
write memory
```
