# Building and receiver setup

These instructions are for developers building from source. To install the
ready-to-run application, use the packages and instructions in
[Releases](https://github.com/Steeod/RF-traffic-monitor/releases).
The PowerShell source bootstrap below is separate from the packaged Setup EXE.

## Build from source on Windows

On a 64-bit Windows 10 or 11 computer, clone the repository and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

The setup asks for a city or region, shows matching OpenStreetMap/Nominatim
results and lets the user choose one. Latitude and longitude can also be passed
directly. It then:

1. Creates the ignored local receiver configuration with the chosen station name
   and coordinates.
2. Downloads all pinned application runtimes, decoder binaries, source archives,
   SDR libraries, Zadig and signed Alfa driver packages. Every downloaded file is
   checked against its expected SHA-256 before extraction.
3. Builds Natural Earth coastlines, OpenStreetMap place labels and an EOXCloudless
   offline satellite pyramid around the station. The default coverage radius is
   200 km, with detailed zoom around the nearest 50 km.
4. Installs Python, Rust and Visual Studio C++ Build Tools through `winget` when
   they are missing, unless `-SkipToolchainInstall` is used.
5. Builds the xng and OpenDroneID native decoders and the Virtual Radar bridge,
   collects dependency licenses, runs the tests and creates
   a portable package under `dist/`.

For unattended location selection, for example:

```powershell
.\setup.ps1 -Latitude 37.9838 -Longitude 23.7275 `
  -StationName "Athens RF Station" -RadiusKm 200 -Receiver RTL -WifiSupport None
```

Use `-Receiver WiFi -WifiSupport Windows` for a station that has only a
compatible Wi-Fi adapter and will monitor Remote ID without an SDR.

The satellite data is optional because EOX 2024 imagery is CC BY-NC-SA 4.0 and
non-commercial. Use `-SkipSatellite -SkipPackage` for a source/dependency build
without it. Map generation requires internet access and can take significant
time and disk space.

### Driver hand-off

RTL-SDR selection is automatic. The saved ADS-B index is tried first; if it
cannot open, other detected RTL receivers are tried. AIS-catcher and the native
decoders enumerate independently and find that same receiver by its USB serial,
so an ADS-B index of 1 can correctly map to native index 0. Indices are not USB
port numbers. Discovery runs when starting reception and changing radio modes.

In **Receiver, station, map, and drivers**, leave **RTL-SDR serial** blank for
automatic selection, or enter a particular receiver's serial. An explicit serial
must match; the app will not substitute another receiver. **Check receiver**
checks the enabled SDR backends with reception stopped and reports the resolved
serial and each backend's own index. Native checks verify USB opening; they do
not prove that a protocol signal can be decoded. No received messages are needed
for discovery. Duplicate or unreadable serial numbers require connecting only
one identifiable receiver or assigning unique serials outside this application.
After replacing a receiver, press Stop and start again to discover it afresh.

Old configurations remain supported; `rtl_serial` defaults to an empty string.
The former proposed `native_device_index` workaround is superseded by automatic
serial matching. Do not copy another computer's `config.json` or `data/radar.log`
into the source repository.

The setup downloads and verifies the drivers, but preserves the safety steps
that require knowing the physical device:

- **RTL-SDR or HackRF:** setup includes the signed Zadig 2.9 executable. If discovery cannot open
  an RTL-SDR because WinUSB is missing, select **Install WinUSB**. In Zadig, select **Options → List All Devices**, choose
  the RTL-SDR's first interface (normally **Bulk-In, Interface 0**) and install
  **WinUSB**. The application cannot safely make the final device selection.
- **AWUS036H/AWUS036ACS with Windows WLAN:** when selected during setup, the
  matching Microsoft-signed driver is installed through `pnputil` after a UAC
  prompt. Windows WLAN scanning does not require Npcap.
- **Npcap raw capture:** install Npcap separately from its official site because
  its installer is not redistributed. Monitor-mode support still depends on the
  adapter and driver.
- **AWUS036ACS through WSL2:** setup downloads the WSL kernel/driver source bundle
  and installs `usbipd-win` after UAC. Windows may require WSL installation and a
  restart; the application then guides USB binding and the Linux driver build.

All downloads are cached under `downloads/`, so rerunning setup after a restart
or interrupted toolchain installation resumes without downloading valid files again.

The dashboard also checks connected Alfa hardware IDs. If a supported adapter
is present without a usable driver, it displays a prominent driver-required
message and an **Install bundled driver** button. RTL-SDR `usb_open error -5`
is reported as a WinUSB/device-busy problem instead of a generic receiver error.
HackRF error `-5` is reported as a busy or locked device; close other SDR tools
or reconnect the device before retrying. A successfully opened receiver can
still show no targets when the antenna, gain, frequency coverage, local traffic,
or reception conditions do not provide decodable signals.

## Development without the full bootstrap

Use Python 3.12 on Windows. Create local settings before running the application
or tests; keep an existing configuration if one is already present:

```powershell
if (!(Test-Path app/config.json)) { Copy-Item app/config.example.json app/config.json }
Push-Location tests
python -m unittest test_radar.ModelTests test_radar.ProcessTests -v
Pop-Location
```

That command runs the model and process tests available without vendor binaries.
You can also run `python -m unittest discover -s tests -v` from the repository
root; checks that require dependencies generated by setup are skipped until those
files exist. After provisioning, the same command runs the complete suite.

The Python controller uses the standard library. Satellite preparation uses a
pinned Pillow build installed by setup. Native reception requires the upstream binaries and libraries
listed in the credits. `Start.cmd` expects `app/runtime/python.exe`; developers
with Python installed can run `python app/server.py` after provisioning the
dependencies. Missing maps or decoders limit the available functionality.

`tools/prepare.py` downloads and lays out the complete external dependency set.
The native build requires Rust/MSVC, Visual Studio C++ Build Tools and upstream
sources at `.build/xng-0.21.0` and `.build/opendroneid-core-c-master`.
See [native build notes](../tools/BUILD.md). The root `setup.ps1` automates these
steps for a clean Windows checkout.

Satellite tests are skipped when the satellite manifest is absent. To rebuild
the optional imagery after setup, run `python tools/prepare-satellite.py`;
this downloads data and can take considerable time and space.


[Back to the project overview](../README.md)
