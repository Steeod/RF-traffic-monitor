# RF Traffic Monitor 0.10.2 Beta

This release addresses RTL-SDR discovery failures where dump1090 can open
the receiver but the application cannot read its device-list output.

## Changes

- New 32-bit RTL discovery helper uses the same rtlsdr.dll as dump1090.
- Receiver discovery no longer depends on buffered dump1090 console output.
- The helper checks device identity and verifies that the receiver can be opened and closed.
- Discovery commands, exit status, output and errors are logged in data/radar.log.
- Explicit serial selection never falls back to a different receiver.
- Ambiguous duplicate serials are rejected.
- Automatic selection can try another receiver if the preferred receiver is busy.
- Includes the previous offline map and RTL-SDR V4 runtime fixes.
- Adds the blue RFT particle-wave icon to the Setup executable, installer window and browser tab.

## Downloads

Download the packages from the
[0.10.2 Beta release page](https://github.com/Steeod/RF-traffic-monitor/releases/tag/v0.10.2-beta.1).

- New installation: RFTrafficMonitor-0.10.2-Setup-win64.exe
- Existing installation: RFTrafficMonitor-0.10.2-update.zip
- Package checksums: SHA256SUMS-0.10.2.txt

GitHub's automatic source archives are not ready-to-run application packages.

## Updating from 0.10 or 0.10.1

1. Exit RF Traffic Monitor and close other SDR applications.
2. Back up the application folder.
3. Extract the entire update ZIP into the folder containing Start.cmd.
4. Accept replacement of the included files.
5. Launch Start.cmd and press Ctrl+F5. The tab title should show 0.10.2.
6. Run Check receiver, then test Automatic cycle with only ADS-B selected.

The update includes vendor/adsb/rtl-probe.exe.
Replacing rtl_devices.py alone is not sufficient.

Settings, downloaded maps and logs are preserved.
No manual Python editing is required.
If WinUSB is already correctly installed, this update does not require
reinstalling the driver.

To roll back, exit the application and restore your backup.

## New installation

Run the Setup EXE and select a new or empty folder.
After extraction, launch Start.cmd.

The optional driver download requires internet access.
USB driver installation through Zadig requires selecting the correct device.

## Validation and diagnostics

Automated checks have passed, but real reception on affected RTL-SDR V3/V4
systems still needs confirmation.

The receiver check verifies USB access; it does not confirm antenna
performance or successful aircraft decoding.

If a problem remains, provide the Check receiver result and data/radar.log
privately to the maintainer.

The Windows executables are unsigned.
Optional Npcap and WSL setup remains separate.
