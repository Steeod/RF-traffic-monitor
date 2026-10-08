# RF Traffic Monitor 0.10.3 beta

Technology buttons start and stop reception immediately. ADS-B, AIS, ACARS,
VDL2, HFDL and RS41 share the selected SDR; Wi-Fi Remote ID runs in parallel.
One selected SDR technology runs continuously. With several selected, the
existing ADS-B priority schedule applies. Deselect all, or press Stop all, to
stop reception. Startup remains stopped until a technology is selected.

First-run setup asks for station name, receiver, location and map radius
(50, 100 or 200 km). Type a country, city or island (for example Rhodes, Greece);
online results appear after a short pause. Choose the correct result to fill
latitude and longitude automatically. Manual coordinates remain available.
The chosen coordinates set both station and map centre.
Download the offline map immediately or later. Existing configured stations
are preserved. Station and map setup can be reopened at any time; stop before
saving. Demo targets use the visible packaged map region when setup is missing.

Setup creates an RFTrafficMonitor subfolder beside its EXE by default.
For example, C:\Radio\Setup.exe installs into C:\Radio\RFTrafficMonitor.
Browse remains available; the displayed path is the final application folder.
Existing application paths are checked before extraction; existing installations
must use the update ZIP. Unrelated files in the destination are preserved.

Logs now record decoder/bridge health and message totals every 30 seconds.
The VRS bridge logs SBS connection changes and received/translated line counts.
These distinguish connection/parser issues from a decoder producing no SBS data;
they do not measure antenna performance or prove why no radio frames arrive.

## Update an existing installation

1. Exit the application using Exit and back up its folder.
2. Extract RFTrafficMonitor-0.10.3-update.zip into the folder containing Start.cmd.
3. Replace all included files, including vendor/vrs/VrsBridge.exe.
4. Run Start.cmd and refresh the browser with Ctrl+F5. Check version 0.10.3.
5. Complete Station and map setup if prompted. Existing configuration, maps and
   logs are retained. Select Aircraft / ADS-B alone for the reception test.

## New installation

Place RFTrafficMonitor-0.10.3-Setup-win64.exe in the desired parent folder,
run it and accept the displayed RFTrafficMonitor subfolder, or choose another
destination. Run Start.cmd inside the new subfolder afterwards and complete the station/map setup. Drivers are optional
downloads; selecting and installing a USB driver still requires the usual
receiver-specific steps.

## Upload source and release files to GitHub

1. Extract RFTrafficMonitor-0.10.3-source-update.zip in a temporary folder.
2. In the existing repository create branch codex/update-0.10.3.
3. Upload the extracted app/, tools/, tests/ folders and UPDATE-0.10.3.md with
   their relative paths intact. Do not upload the entire workspace, private
   config.json, logs, downloaded maps or the source ZIP as a source file.
4. Commit: Add station setup and direct technology scanning controls.
5. Open and review a pull request, then merge after validation.
6. Draft a release from the merged commit with tag v0.10.3-beta.1 and title
   RF Traffic Monitor 0.10.3 Beta - Station setup and continuous reception.
7. Attach RFTrafficMonitor-0.10.3-update.zip,
   RFTrafficMonitor-0.10.3-Setup-win64.exe and SHA256SUMS-0.10.3.txt.
   The source-update ZIP is for updating the repository, not for end users.
8. Mark this as a pre-release. Follow PUBLISHING.md and retain third-party
   notices and bundled source archives. Publish when ready.

Suggested release description:

- First-run station, receiver and offline map setup with country/city/island search.
- Individual technology buttons automatically control scanning.
- Continuous reception with one selected SDR technology; deselect all to stop.
- Demo positions follow the map when location has not yet been configured.
- Portable Setup creates its own RFTrafficMonitor subfolder and protects existing files.
- Better ADS-B connection and message diagnostics.

Real RF reception still requires a hardware test. A successful USB check does
not prove reception, antenna suitability or decoded aircraft. This release
removes unnecessary restarts but does not claim to resolve Paolo's zero-message
report before his next test.

## Place-search service

Search uses Photon (https://github.com/komoot/photon), based on OpenStreetMap
data (ODbL). The typed place query is sent to photon.komoot.io after a short
pause; no station name, saved coordinates or receiver data is sent. Requests
are throttled and cached for the running session. Internet is needed for new
searches and map downloads; manual coordinates and existing offline maps remain
available without it. Selecting a result does not download a map: saving with
the download checkbox selected starts that separate action.

These rebuilt 0.10.3 packages replace the earlier unpublished 0.10.3 files. Use
all files from this build, including its regenerated SHA256SUMS-0.10.3.txt.
