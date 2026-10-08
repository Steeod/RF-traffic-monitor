# RF Traffic Monitor

**Monitor aircraft, vessels, radiosondes and compatible drones on Windows.**
Created by **Steeod**.

RF Traffic Monitor brings signals received at your own station into a local
map and message dashboard. It supports RTL-SDR and HackRF receivers, with
optional Wi-Fi Remote ID through a separate compatible adapter.

**[Downloads and release notes](https://github.com/Steeod/RF-traffic-monitor/releases)**

## What it supports

- **Aircraft:** ADS-B, ACARS, VDL2 and HFDL.
- **Vessels:** AIS.
- **Radiosondes:** RS41.
- **Drones:** compatible Wi-Fi Remote ID broadcasts.
- Offline maps, configurable station location and a demo without an SDR.

Reception depends on compatible hardware, drivers, antenna and local signals.

## Get started

1. Open [Releases](https://github.com/Steeod/RF-traffic-monitor/releases) and choose
   a release. Beta versions are marked as pre-releases.
2. For a new installation, download its **Setup EXE**. To update an existing
   installation, download its **update ZIP** and follow that release's instructions.
3. Run `Start.cmd` from the application folder and configure your station,
   receiver and map.
4. Select the technologies to receive. One selected SDR technology runs
   continuously; multiple technologies share the SDR. Deselect all to stop.

The packaged application runs on **64-bit Windows 10/11** and includes its
runtime and decoders. Internet is needed for online place searches and new map
downloads; the dashboard and downloaded maps run locally.

## Updates and help

Changes, fixes, installation details and known limitations are listed with each
[release](https://github.com/Steeod/RF-traffic-monitor/releases).

For a problem, open an [issue](https://github.com/Steeod/RF-traffic-monitor/issues)
with the application version, receiver model and steps to reproduce it.

For development, see [building and receiver setup](docs/BUILDING.md) and
[native decoder build notes](tools/BUILD.md).

## License

Project-authored code is [MIT licensed](LICENSE). See
[license scope](LICENSE-STATUS.md) and [third-party credits](THIRD-PARTY.md).
Optional EOX satellite imagery is CC BY-NC-SA 4.0 (non-commercial).
