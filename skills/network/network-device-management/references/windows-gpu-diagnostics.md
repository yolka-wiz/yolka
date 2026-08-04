# Windows GPU Diagnostics via WinRM

Remote diagnostic workflow for GPU/display issues on Windows desktops and workstations, using pywinrm + nvidia-smi + WMI + PowerShell.

## When to Use

- User reports video lag, stuttering, or intermittent black screens on a Windows computer
- User says "unplugging and replugging the HDMI cable fixes it temporarily"
- GPU-related event log errors or TDRs suspected
- Need to check driver version, PCIe link state, power management, or Memory Integrity (HVCI) status remotely

## Quick Connection

```python
import winrm
s = winrm.Session('<host>', auth=('<user>', '<pass>'), transport='ntlm')
```

- Port 5985 (HTTP) first; 5986 (HTTPS) if HTTP fails
- Transport: `ntlm` is most compatible for domain or local accounts
- Test: `s.run_cmd('cmd.exe', ['/c', 'hostname'])` → expect exit code 0 with hostname

## Diagnostic Layers (work in order)

### 1. GPU Hardware & Driver Info

```python
# Basic info
r = s.run_cmd('cmd.exe', ['/c', 'nvidia-smi'])
# Check: GPU name, temp, P-State, power usage, VRAM, driver version

# Detailed hardware
r = s.run_cmd('cmd.exe', ['/c', 'wmic path Win32_VideoController get Name,DriverVersion,DriverDate,AdapterRAM,Status /format:csv'])

# PCIe link state (critical for stutter issues)
r = s.run_cmd('cmd.exe', ['/c',
  'nvidia-smi --query-gpu=pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current,pcie.link.width.max --format=csv'])
# If current < max, ASPM may be too aggressive
```

**Key PCIe values for RTX 4060:** Gen 4 x8 (max). Gen 1 at idle = normal with ASPM; failure to reach Gen 4 under load = problem.

**Potential pitfalls with nvidia-smi:** The `-d PCI` flag does not work on modern driver versions. Use `--query-gpu=pcie.*` instead. `WmiMonitorRawEDID` may return empty results over WinRM; use `WmiMonitorID` for monitor identification instead.

### 2. Event Log Analysis (TDR / Driver Crashes)

```powershell
# Fast query with wevtutil (preferred over Get-WinEvent for remote)
wevtutil qe System /q:"*[System[(EventID=1 or EventID=13 or EventID=14 or EventID=4101 or EventID=4102)]]" /c:20 /f:text /rd:true

# Slow but thorough with PowerShell
Get-WinEvent -FilterHashtable @{LogName='System'} -MaxEvents 200 |
  Where-Object { $_.ProviderName -match 'nvlddmkm|dxgkrnl|dxgmms|Display' } |
  Select-Object TimeCreated,Id,LevelDisplayName,Message
```

**Key event IDs:**
- `nvlddmkm` Event ID 13 — NVIDIA driver stopped responding (TDR)
- `nvlddmkm` Event ID 14 — driver recovered from TDR
- `Display` Event ID 4101 (source: Display) — Display driver failed to respond within timeout
- Absence of these events does NOT rule out GPU issues (many intermittent stutters don't trigger TDR)

### 3. HVCI / Memory Integrity Check

This is the **most common cause** of GPU stuttering on Windows 11 with NVIDIA GPUs.

```powershell
Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -Class Win32_DeviceGuard |
  Format-List VirtualizationBasedSecurityStatus,CodeIntegrityPolicyEnforcementStatus,SecurityServicesRunning
```

**Status values to look for:**
- `VirtualizationBasedSecurityStatus: 2` = VBS is ENABLED and running
- `CodeIntegrityPolicyEnforcementStatus: 2` = HVCI (Memory Integrity) is ENFORCED
- `SecurityServicesRunning: {1, 2}` = both HVCI and VBS are actively running

**Diagnosis:** Every NVIDIA driver operation (display buffer scanout, HDMI link training, clock transitions) must pass through the hypervisor for validation. This adds unpredictable latency that accumulates into perceived stutter. The HDMI replug fixes it temporarily because it forces a full display pipeline re-initialization.

**Fix:** Windows Security → Core Isolation → Memory Integrity → Toggle OFF → reboot.

### 4. PCIe ASPM Settings

```powershell
# Check active power scheme
powercfg /getactivescheme

# Check PCIe link state power management
powercfg /query <GUID> SUB_PCIEXPRESS
```

**Index values for ASPM:**
0 = Off (no power saving, best GPU performance)
1 = Moderate power savings (let link sleep but wake promptly)
2 = Maximum power savings (aggressive — can cause link training delays)

A setting of 2 on a desktop's Balanced plan is inappropriate and can cause the GPU's PCIe link to drop to Gen 1 and fail to transition back under load.

```powershell
# Fix: set to Off (0) for maximum stability
powercfg /setacvalueindex <GUID> SUB_PCIEXPRESS ASPM 0
powercfg /setdcvalueindex <GUID> SUB_PCIEXPRESS ASPM 0
powercfg /setactive <GUID>
```

### 5. Monitor / Display Info

```powershell
# Monitor identity
$mon = Get-CimInstance -Namespace root/wmi -Class WmiMonitorID
$mon.UserFriendlyName | ForEach-Object { if ($_ -ne 0) { [char]$_ } }

# Connection type
Get-CimInstance -Namespace root/wmi -Class WmiMonitorConnectionParams |
  Select-Object VideoOutputTechnology
```

**VideoOutputTechnology values:**
5 = HDMI (most common for desktop GPUs)
10 = DisplayPort

### 6. Power Management Settings

```powershell
# Current power plan
powercfg /getactivescheme

# NVIDIA driver power settings (registry)
Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000" |
  Select-Object *Power*,*Perf*,*PState*,*ASPM*,*PCIe*
```

### 7. Clock States and Throttling

```bash
# Check clock throttle reasons
nvidia-smi --query-gpu=clocks_throttle_reasons.active,clocks_throttle_reasons.gpu_idle,clocks_throttle_reasons.applications_clocks_setting --format=csv
```

**Bit decoding:**
- Bit 0 set = GPU Idle (normal at idle)
- Bit 1 = Applications Clocks Setting (user-set power limit)
- Bit 2 = SW Power Cap
- Bit 3 = HW Slowdown (thermal)

## Session Case Study: "HDMI replug fixes stutter"

**Target:** ASUS desktop, Windows 11 Pro, RTX 4060 (8GB), Samsung S22C31x monitor via HDMI

**Symptoms:** Video plays fine initially, then gets progressively laggy/stuttery. Unplugging and replugging the HDMI cable fixes it temporarily.

**Findings (in order of significance):**

| Finding | Status | Impact |
|---|---|---|
| HVCI (Memory Integrity) | ENABLED and RUNNING | HIGH — adds hypervisor latency to every GPU display operation |
| PCIe ASPM | Maximum power savings (index 2) | HIGH — forces PCIe to Gen 1, may fail to transition back properly |
| PCIe link (idle) | Gen 1 x8 (max: Gen 4 x8) | Root cause enabler — combined with HVCI causes display pipeline timing failures |
| Driver | 591.86 (Jan 2026) | Latest, not a factor |
| GPU temp / power | 46°C, 55W idle, P8 state | Normal |
| Event log TDR events | None found | No explicit driver crash — intermittent link training issue, not TDR |
| Monitor | Samsung S22C31x, 1080p60, no HDR | Budget monitor — possible EDID/link training quirks |

**Mechanism hypothesis:**
HVCI intercepts every GPU driver DMA operation for validation. When the GPU needs to transition from idle (P8, PCIe Gen 1) to active (video playback), the hypervisor adds unpredictable millisecond-range latency to: PCIe link re-negotiation, display buffer scanout, HDMI link training (FRL on HDMI 2.1). This causes frame drops that accumulate into perceived stutter. The HDMI replug forces a complete pipeline reset (EDID re-read, fresh FRL training, buffer re-initialization), which temporarily clears the accumulation.

**Recommended fixes:**
1. Turn off Memory Integrity (HVCI) in Windows Security → Core Isolation → reboot
2. Change PCIe ASPM from "Maximum" to "Off" or "Moderate" via powercfg
3. If still present, replace HDMI cable with a certified HDMI 2.1 cable (48Gbps)
4. NVIDIA Control Panel → Power Management Mode → "Prefer Maximum Performance"

## Common Pitfalls

- **`nvidia-smi -d PCI`** does not work on modern drivers. Use `--query-gpu=pcie.link.gen.current,...` instead.
- **`WmiMonitorRawEDID`** often returns empty results over WMI/WinRM. Use `WmiMonitorID` for monitor identification.
- **`pywinrm.run_ps()` is slow** for large event log queries. Use `wevtutil` via `run_cmd()` for performance, or limit `-MaxEvents` to 50-200.
- **`Win32_VideoController.AdapterRAM` may lie** — RTX 4060 has 8GB VRAM but WMI reports ~4GB. Use `nvidia-smi` for accurate VRAM.
- **No TDR events doesn't mean no GPU problem** — intermittent link training issues don't trigger TDR; they manifest as stutter only.
- **VBS registry key** (`EnableVirtualizationBasedSecurity`) may not exist even when VBS is running (enforced via group policy or default Windows 11 settings). Check via `Win32_DeviceGuard` WMI class instead.
- **Hyper-V Platform feature may show Disabled** even when VBS is running — Windows 11 uses a minimal hypervisor for VBS that doesn't require the full Hyper-V role.
