# VMware ESXi Networking Debugging

Commands and workflow for investigating bridge forwarding issues from a VM
perspective when containers behind a Linux bridge can't reach external hosts.

## When to Use

- Linux bridge forwards between host and container but not to/from external hosts
- ARP resolves across the bridge but data packets don't flow
- Suspect MAC filtering at the hypervisor or physical switch level
- Need to verify port group security policy without UI access

## Prerequisites

SSH access to the ESXi host (`vim-cmd` and `esxcli` available).

## Investigation Workflow

### 1. Identify the VM and its networks

```bash
# List all VMs — find your VM's name and VMID
vim-cmd vmsvc/getallvms

# Get which networks (port groups) a VM is connected to
vim-cmd vmsvc/get.networks <vmid>
```

### 2. Map NICs to port groups and MACs

```bash
# Dump VM devices — look for VirtualEthernetCard sections
vim-cmd vmsvc/device.getdevices <vmid>
```

Each NIC shows:
- `deviceName = "<PortGroup Name>"`
- `network = 'vim.Network:HaNetwork-<PortGroup Name>'`
- `macAddress = "00:0c:29:xx:xx:xx"`

### 3. List all port groups on the vSwitch

```bash
esxcli network vswitch standard portgroup list
# Shows: Name, Virtual Switch, Active Clients, VLAN ID
```

### 4. Check port group security policy

```bash
esxcli network vswitch standard portgroup policy security get -p '<PortGroup Name>'
```

Key fields:
| Field | Normal | Problem |
|-------|--------|---------|
| `Allow Promiscuous` | false | Must be `true` for multiple MACs |
| `Allow MAC Address Change` | true | false → new MACs blocked |
| `Allow Forged Transmits` | true | false → container MAC blocked |

### 5. Check vSwitch-level defaults

```bash
esxcli network vswitch standard policy security get -v vSwitch0
```

Port groups inherit from vSwitch unless overridden (`Override Vswitch ...: true`).

### 6. Check failover and uplinks

```bash
esxcli network vswitch standard portgroup policy failover get -p '<PortGroup Name>'
```

Shows which physical NICs (vmnic0-3) the port group uses.

## Interpreting Results

**If VMware security is permissive** (MAC changes + forged transmits allowed):
- The problem is at the **physical switch** level (MAC limit, port-security, sticky MAC)
- Solution: NAT/routed mode for containers (avoids L2 MAC issues entirely)

**If VMware security is restrictive**:
- Change the port group settings in the VMware UI or via esxcli
- `esxcli network vswitch standard portgroup policy security set -p 'PG' --allow-mac-change=true --allow-forged-transmits=true`

## Common Scenario: Bridge MAC Mismatch

See `server-iac-provisioning` skill, pitfall "Bridge MAC mismatch". The bridge gets a random MAC different from the physical NIC. Fix:

```bash
# Align bridge MAC to NIC MAC
sudo ip link set br13 address $(cat /sys/class/net/ens224/address)
sudo incus restart <container-name>
```

## Related

- `server-iac-provisioning` skill — full bridge/incus setup and debugging workflow
- `remote-server-operations` skill — double-hop SSH patterns for ESXi access through a jump box
