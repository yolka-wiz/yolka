# GPU / Display Diagnostics via WinRM

## Overview

Debugging GPU issues (stuttering, TDR, display link problems) on Windows via WinRM remote investigation. The symptom pattern "video lags consistently, then HDMI unplug/replug fixes it temporarily" is a **display link training / timing issue** — not GPU hardware failure.

## Quick Assessment

```python
import winrm
s = winrm.Session(host, auth=(user, pw), transport='ntlm')
```

### GPU Hardware Info
```powershell
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, DriverDate, AdapterRAM, Status

# Via nvidia-smi (more reliable)
nvidia-smi --query-gpu=index,name,driver_version,pstate,temperature.gpu,power.draw,utilization.gpu,memory.used --format=csv
```

### PCIe Link Status (NVIDIA)
```powershell
nvidia-smi --query-gpu=pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current,pcie.link.width.max --format=csv
```

Expected for RTX 4060: current=4, max=4, width=8, max=8 at load. At idle, current may drop to gen 1 (normal GPU power saving).

### Performance State & Clock Reasons
```powershell
nvidia-smi -q -d PERFORMANCE
nvidia-smi --query-gpu=clocks_throttle_reasons.active,clocks_throttle_reasons.gpu_idle --format=csv
```

## Root Cause Checklist

### 1. Check Memory Integrity (HVCI) — Primary Suspect

Memory Integrity (Hypervisor-Protected Code Integrity) forces every GPU driver DMA op through the hypervisor, adding unpredictable latency. Known cause of stuttering on NVIDIA GPUs.

```powershell
Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard |
    Select-Object VirtualizationBasedSecurityStatus, CodeIntegrityPolicyEnforcementStatus
```

**Interpretation:**
- `VirtualizationBasedSecurityStatus: 2` = running, `0` = off
- `CodeIntegrityPolicyEnforcementStatus: 2` = enforced, `0` = off
- If both are 2 → HVCI is actively validating every GPU operation

**Fix:** Windows Security → Core Isolation → Memory Integrity → Off → Reboot.

### 2. Check PCIe ASPM Power Management

Aggressive PCIe Link State Power Management drops the link to Gen 1 L1 deep sleep. Transitioning back to Gen 4 under load can fail or add latency.

```powershell
powercfg /getactivescheme
powercfg /query <GUID> SUB_PCIEXPRESS
```

**Interpretation:**
- Index 2 = Maximum power savings (most aggressive)
- Index 1 = Moderate savings
- Index 0 = Off

**Fix (no reboot):**
```powershell
powercfg /setacvalueindex <GUID> SUB_PCIEXPRESS ASPM 0
powercfg /setdcvalueindex <GUID> SUB_PCIEXPRESS ASPM 0
powercfg /setactive <GUID>
```

### 3. Event Logs — TDR Detection

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'} -MaxEvents 200 |
    Where-Object { $_.ProviderName -match 'nvlddmkm|dxgkrnl|dxgmms|Display' -and
                   $_.Id -in (0,1,13,14,4101,4102) } |
    Select-Object TimeCreated,Id,ProviderName,Message | Format-Table -AutoSize -Wrap
```

- Event ID 4101 = "Display driver stopped responding and has recovered" (TDR)
- Event 0x153 from Display = "Display driver failed to respond within the timeout period"
- No events found does NOT rule out TDR — they may have been cleared or rotated out

### 4. Monitor Info

```powershell
# Monitor make/model/year
Get-CimInstance -Namespace root/wmi -Class WmiMonitorID |
    Select-Object ManufacturerName, ProductCodeID, YearOfManufacture

# Connection type: 5=HDMI, 10=DisplayPort
Get-CimInstance -Namespace root/wmi -Class WmiMonitorConnectionParams |
    Select-Object VideoOutputTechnology

# Current resolution, refresh rate, scan mode
Get-CimInstance Win32_VideoController |
    Select-Object CurrentHorizontalResolution, CurrentVerticalResolution, CurrentRefreshRate, CurrentScanMode
```

### 5. Power Plan

```powershell
powercfg /getactivescheme
```

"Balanced" is normal. Set PCIe ASPM appropriately within it.

## Common Root Cause Chain

1. HVCI is ON → adds latency to all GPU driver ops
2. PCIe ASPM = Maximum → link drops to Gen 1 deep sleep
3. Video playback starts:
   - GPU wakes from P8 → re-negotiates PCIe Gen 1→4
   - Every step validated by hypervisor (HVCI)
   - Latency causes display scanout to miss VSYNC → stutter
4. HDMI replug forces full re-init (EDID re-read, link re-train, buffer re-allocate) → temporary fix until cycle repeats

**Fix priority:**
1. Turn OFF Memory Integrity (HVCI) — reboot required
2. Set PCIe ASPM to Off or Moderate — instant
3. Certified HDMI 2.1 cable if link training keeps failing
4. NVIDIA Control Panel → Power Management Mode → "Prefer Maximum Performance"

## Tools Reference

| Tool | Use Case |
|------|----------|
| `nvidia-smi` | GPU status, PCIe link, clocks, temp, power |
| `Get-WinEvent` | TDR events, driver crashes |
| `powercfg` | Power plan, PCIe ASPM settings |
| `Get-CimInstance Win32_VideoController` | Driver version, display mode |
| `WmiMonitorID` | Monitor make/model/year |
| `reg query ... DeviceGuard` | HVCI/VBS registry status |
