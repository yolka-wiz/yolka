# Cisco SSH Troubleshooting: Old IOS + Modern SSH Clients

## The Problem

Cisco Catalyst switches running IOS 12.2 / 15.0 / early 15.2 have SSH servers
that only support algorithms long-deprecated by modern clients:

| Component | Switch offers | OpenSSH 10.3 status | Paramiko 5.0 status |
|-----------|--------------|---------------------|---------------------|
| Key exchange | `diffie-hellman-group1-sha1` (768-bit) | Removed | Removed |
| Host key | `ssh-rsa` | Disabled by default | Disabled by default |
| Ciphers | `aes128-cbc, 3des-cbc, aes192-cbc, aes256-cbc` | CBC disabled by default | Present but negotiable |
| RSA key size | 512-bit (default) | Rejected (< 1024 minimum) | Rejected (< 1024 minimum) |

## Diagnosis Walkthrough

### Verify SSH is enabled at all

```
SW-F0#show ip ssh
SSH Enabled - version 2.0
Authentication timeout: 120 secs; Authentication retries: 3
```

On IOS 15.2(4)E10 the output is richer:

```
SW-CORE#show ip ssh
SSH Enabled - version 2.0
Authentication methods:publickey,keyboard-interactive,password
Authentication Publickey Algorithms:x509v3-ssh-rsa,ssh-rsa
Hostkey Algorithms:x509v3-ssh-rsa,ssh-rsa
Encryption Algorithms:aes128-ctr,aes192-ctr,aes256-ctr,aes128-cbc,3des-cbc,aes192-cbc,aes256-cbc
MAC Algorithms:hmac-sha1,hmac-sha1-96
Authentication timeout: 120 secs; Authentication retries: 3
Minimum expected Diffie Hellman key size : 1024 bits
```

Note: Even IOS 15.2 doesn't show KEX algorithms in `show ip ssh` — they
default to only `diffie-hellman-group1-sha1` unless explicitly configured.

### Check RSA key size

```
SW-F0#show crypto key mypubkey rsa
% Key pair was generated at: 00:11:06 UTC Mar 1 1993
Key name: SW-F0.borna
 Storage Device: private-config
 Usage: General Purpose Key
 Key is not exportable.
 Key Data:
  307C300D 06092A86 4886F70D 01010105 00036B00 30680261 00C8D98D ...
```

**Determining key size from the hex data:**

The first DER tag byte(s) encode the total length of the RSA public key:

| Bytes | Decoded length | Key size |
|-------|---------------|----------|
| `307C` | 124 bytes | **512-bit** |
| `3081 9F` | 159 bytes | **1024-bit** |
| `3082 01 0A` | 266 bytes | **2048-bit** |

- `30` = SEQUENCE tag in ASN.1 DER
- If the length byte is < 128, it's the length itself (e.g. `7C` = 124)
- If the length byte is `81`, the next byte is the length (e.g. `81 9F` = 159)
- If the length byte is `82`, the next 2 bytes are the length

The old Cisco default (`crypto key generate rsa` without `modulus 2048`)
produces a 512-bit key → hex starts with `307C`.

### Client-side: full algorithm negotiation failure

Testing with `ssh -vvv`:

```
$ ssh -vvv a.alavi@192.168.1.100

# Step 1: KEX negotiation fails
debug2: KEX algorithms: (client offers many modern ones)
debug2: peer server KEXINIT proposal
debug2: KEX algorithms: diffie-hellman-group1-sha1
Unable to negotiate: no matching key exchange method found

# Step 2: After adding KEX, host key fails
$ ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 ...
debug1: kex: algorithm: diffie-hellman-group1-sha1
debug1: kex: host key algorithm: (no match)
Unable to negotiate: no matching host key type found. Their offer: ssh-rsa

# Step 3: After adding host key, cipher fails
$ ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 -oHostKeyAlgorithms=+ssh-rsa ...
Unable to negotiate: no matching cipher found. Their offer: aes128-cbc,...

# Step 4: After adding cipher, key length fail
$ ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 -oHostKeyAlgorithms=+ssh-rsa \
       -oCiphers=+aes128-cbc -oMACs=+hmac-md5 ...
debug1: SSH2_MSG_KEX_ECDH_REPLY received
ssh_dispatch_run_fatal: Connection to ... port 22: Invalid key length
```

The 512-bit RSA host key is the final blocker — OpenSSH 10.3 hard-rejects
it regardless of client configuration.

## Reference: Fixed switch config (IOS 15.x+)

For switches that support it, the fix is:

```
conf t
!
! Generate a proper 2048-bit RSA key (overwrites existing)
crypto key generate rsa modulus 2048
!
! Add modern KEX algorithms
ip ssh server algorithm kex diffie-hellman-group14-sha1
ip ssh server algorithm kex diffie-hellman-group-exchange-sha256
!
! Optional: restrict to AES-CTR ciphers
ip ssh server algorithm encryption aes128-ctr aes256-ctr
!
! Optional: restrict MACs
ip ssh server algorithm mac hmac-sha2-256 hmac-sha2-512
!
end
write memory
```

### Feature support by IOS version

| IOS version | `crypto key generate rsa` | `ip ssh server algorithm kex` |
|-------------|--------------------------|-------------------------------|
| 12.2(55)SE3 | Yes — but only 512/1024/2048 | **No** — command doesn't exist |
| 15.0(2)SE11 | Yes — up to 2048 | **Maybe** — depends on feature set |
| 15.2(2)E9 | Yes | **Maybe** — check with `?` |
| 15.2(4)E10 | Yes | **Yes** — fully supported |

On IOS 12.2(55)SE3 only the RSA key can be regenerated; algorithm upgrades
are not possible.
