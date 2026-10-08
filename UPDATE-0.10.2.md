# RF Traffic Monitor 0.10.2 beta

This version replaces ADS-B discovery based on dump1090 text output with a
32-bit helper using the same rtlsdr.dll as dump1090. It enumerates USB serials,
checks the selected identity again, opens and closes the receiver, and returns
structured JSON. Discovery no longer relies on buffered console output or a
two-second forced termination of dump1090. Normal reception remains unchanged.

The helper logs its command, exit status, stdout and stderr to data/radar.log.
Timeouts and process startup errors are logged. Duplicate serials are rejected;
an explicitly selected serial never falls back to another receiver. Automatic
selection can try another receiver if the preferred one is busy. Previous map
and V4 library fixes are included.

## Existing users (0.10 or 0.10.1)

1. Exit RF Traffic Monitor and close other SDR applications.
2. Back up the application folder.
3. Extract RFTrafficMonitor-0.10.2-update.zip into the folder containing Start.cmd.
4. Accept replacement of the included files. The new vendor/adsb/rtl-probe.exe
   must also be extracted; replacing rtl_devices.py alone is not sufficient.
5. Launch Start.cmd and press Ctrl+F5. The tab title should show 0.10.2.
6. Run Check receiver, then test Automatic cycle with only ADS-B selected.

Settings, maps and logs are preserved. No manual Python editing or driver
reinstallation is required. To roll back, exit and restore your backup.
New users can use RFTrafficMonitor-0.10.2-Setup-win64.exe in an empty folder.

Real reception on Paolo's receiver is still awaiting confirmation. Send the
Check receiver result and the new data/radar.log privately if a problem remains.
The helper confirms USB opening, not antenna performance or decoded aircraft.

## GitHub upload

1. Extract RFTrafficMonitor-0.10.2-source-update.zip locally.
2. In the repository root, choose Add file > Upload files. Drag the extracted
   app/, tools/, tests/ folders and UPDATE-0.10.2.md, retaining their paths.
3. Commit message: `Fix RTL receiver discovery and diagnostics`.
4. Create branch codex/update-0.10.2, create a pull request, review and merge.
   Compare any newer independent changes before replacing files.
5. Choose Releases > Draft a new release. Create tag v0.10.2-beta.1 on the
   branch containing the merged changes (normally main).
6. Title: `RF Traffic Monitor 0.10.2 Beta - RTL discovery fix`.
7. Attach RFTrafficMonitor-0.10.2-update.zip,
   RFTrafficMonitor-0.10.2-Setup-win64.exe, and SHA256SUMS-0.10.2.txt.
8. Select This is a pre-release. Save draft while completing the existing
   public distribution checks in PUBLISHING.md; Publish release makes it public.

Suggested release description:

```markdown
Fixes ADS-B receiver discovery when dump1090 opens the receiver but its
device-list text is unavailable to the application.

### Changes
- New 32-bit RTL discovery helper reads USB device identities directly.
- No dependency on dump1090 console output or its discovery timeout.
- Detailed discovery output and errors are recorded in data/radar.log.
- Preserves explicit serial selection and rejects ambiguous duplicate serials.
- Includes the previous map and RTL-SDR V4 runtime fixes.

### Updating from 0.10 or 0.10.1
Close the application and back up its folder. Extract the update ZIP into
the folder containing Start.cmd, replacing files. Start the application
and press Ctrl+F5. Configuration, maps and logs are preserved.
Extract the entire patch: it includes a new rtl-probe.exe helper.

### New installation
Use the Setup EXE and choose an empty folder.

### Validation
Automated checks are included. Real V3/V4 reception on affected computers
still needs confirmation. Please test Check receiver and ADS-B only first,
and send data/radar.log privately if a problem remains.
The binaries are unsigned. Optional Npcap/WSL setup remains separate.
```

Official instructions: https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
