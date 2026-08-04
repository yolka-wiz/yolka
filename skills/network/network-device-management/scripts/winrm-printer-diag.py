#!/usr/bin/env python3
"""
Remote printer diagnosis via WinRM.
Checks printer status, queue, event logs, drivers, and USB connectivity.
Usage: python winrm_printer_diag.py <host> <username> <password> "<printer-name>"
"""
import winrm, sys, time

def run(sess, cmd, label=""):
    if label:
        print(f"=== {label} ===")
    r = sess.run_ps(cmd)
    out = r.std_out.decode(errors='replace') if r.std_out else ""
    err = r.std_err.decode(errors='replace') if r.std_err else ""
    if '#< CLIXML' in err:
        err = ''
    if out.strip():
        print(out[:2000].strip())
    if err.strip():
        print(f"[err] {err[:200]}")

if len(sys.argv) < 4:
    print(f"Usage: {sys.argv[0]} <host> <user> <pass> [\"printer-name\"]")
    sys.exit(1)

host = sys.argv[1]
user = sys.argv[2]
pwd = sys.argv[3]
printer = sys.argv[4] if len(sys.argv) > 4 else None

sess = winrm.Session(f'http://{host}:5985/wsman', auth=(user, pwd), transport='ntlm')

print("=" * 60)
print(f"PRINTER DIAGNOSIS: {host}")
print("=" * 60)

# Host info
run(sess, 'hostname', "Hostname")

# All printers
run(sess, 'Get-Printer | Select-Object Name, DriverName, PortName, PrinterStatus, JobCount | Format-Table -AutoSize', "All printers")

if printer:
    # Specific printer status
    run(sess, f'$p = Get-CimInstance Win32_Printer -Filter "Name = \'{printer}\'"; '
              f'Write-Output "PrinterStatus: $($p.PrinterStatus) (3=Idle, 4=Printing/Unknown)"'
              f'Write-Output "DetectedErrorState: $($p.DetectedErrorState) (0=NoError)"'
              f'Write-Output "PrinterState: $($p.PrinterState) (0=Idle, 1024=IO_ACTIVE)"'
              f'Write-Output "WorkOffline: $($p.WorkOffline)"'
              f'Write-Output "DriverName: $($p.DriverName)"', f"Status: {printer}")
    
    # Print queue
    run(sess, f'Get-PrintJob -PrinterName "{printer}" -ErrorAction SilentlyContinue | '
              f'Select-Object Id, DocumentName, JobStatus, JobSize, TimeSubmitted | Format-Table -AutoSize', "Print queue")
    
    # Print driver info
    run(sess, f'Get-PrinterDriver -Name "*" | Where-Object {{ $_.Name -match "$( (Get-Printer -Name \"{printer}\").DriverName )" }} | '
              f'Select-Object Name, MajorVersion, Path, HardwareID | Format-List', "Driver details")
    
    # Driver file integrity
    run(sess, f'$driver = Get-PrinterDriver -Name (Get-Printer -Name "{printer}").DriverName; '
              f'$driver.DependentFiles | ForEach-Object {{ if (Test-Path $_) {{ Write-Output "OK: $_" }} else {{ Write-Output "MISSING: $_" }} }}',
              "Driver file check")

# Print service errors (last 24h)
run(sess, 'Get-WinEvent -LogName "Microsoft-Windows-PrintService/Admin" -MaxEvents 30 -ErrorAction SilentlyContinue | '
          'Where-Object { $_.TimeCreated -gt (Get-Date).AddDays(-1) } | '
          'Select-Object TimeCreated, Id, LevelDisplayName, @{N="Msg";E={$_.Message.Substring(0, [Math]::Min(200, $_.Message.Length))}} | '
          'Format-Table -AutoSize -Wrap', "Print service errors (24h)")

# USB printer devices
run(sess, 'Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPClass -eq "Printer" -or $_.PNPClass -eq "USB" -and $_.Name -match "Printer|LaserJet|HP" } | '
          'Select-Object Name, DeviceID, Status, ConfigManagerErrorCode | Format-Table -AutoSize', "USB printer devices")

# Spooler files
run(sess, 'Get-ChildItem "C:\\Windows\\System32\\spool\\PRINTERS" -ErrorAction SilentlyContinue | '
          'Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize', "Spooler temp files")

# Driver folder files
run(sess, 'Get-ChildItem "C:\\Windows\\System32\\spool\\DRIVERS\\x64\\3" -ErrorAction SilentlyContinue | '
          'Select-Object Name, Length | Format-Table -AutoSize', "Driver folder files")
