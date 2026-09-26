# Third-party components

Project-authored code is licensed under MIT; see the repository's root `LICENSE`.
That license does not replace the third-party terms listed here.

For the source repository, see `../THIRD-PARTY.md` for the expanded provenance
review and `../PUBLISHING.md` for unresolved public-release requirements.
The notes below describe the local development package, not a clearance to
redistribute every bundled binary or driver.

This is a local development package, with original third-party licenses preserved.
The controller/UI and VrsBridge source are included. Upstream sources and build
instructions are available at the following canonical repositories.

| Component | Source | License |
|---|---|---|
| Virtual Radar Server 2.4.4 libraries | https://github.com/vradarserver/vrs | BSD-3-Clause |
| dump1090 1.10.3010.14 | https://github.com/MalcolmRobb/dump1090 | BSD-2-Clause (see source notices) |
| RTL-SDR Blog driver V1.4.0 | https://github.com/rtlsdrblog/rtl-sdr-blog/tree/V1.4.0 | GPL-2.0 |
| AIS-catcher v0.70 | https://github.com/jvde-github/AIS-catcher/tree/v0.70 | GPL-3.0 |
| Python 3.12.10 embeddable | https://www.python.org/downloads/release/python-31210/ | PSF (runtime/LICENSE.txt) |
| Natural Earth land 1:10m | https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/ | Public domain |
| EOxCloudless Sentinel-2 2024 | https://cloudless.eox.at/license-non-commercial | CC BY-NC-SA 4.0 |
| OpenStreetMap settlements extract | https://www.openstreetmap.org/copyright | ODbL 1.0 |
| xng 0.21.0 DSP cores | https://github.com/airframesio/xng/tree/v0.21.0 | MIT OR Apache-2.0; crate provenance notices retained |
| libacars (ported within xng-acars) | https://github.com/szpajder/libacars | MIT; upstream provenance credits Tomasz Lemiech (2018–2023) |
| OpenDroneID core C | https://github.com/opendroneid/opendroneid-core-c | Apache-2.0 |
| Realtek RTL8187/RTL8811AU drivers | Microsoft Update Catalog | Redistribution terms unresolved; signatures do not grant redistribution rights |
| usbipd-win 5.3.0 | https://github.com/dorssel/usbipd-win/tree/v5.3.0 | GPL-3.0; corresponding source must be addressed before distributing the MSI |
| aircrack-ng RTL8812AU/8811AU | https://github.com/aircrack-ng/rtl8812au/tree/v5.6.4.2 | Retain GPL v2 family and file-specific notices |
| rtw88 backport | https://github.com/lwfinger/rtw88 | Retain code and firmware-specific notices; current archive uses master |
| WSL2 Linux kernel source 6.6.87.2 | https://github.com/microsoft/WSL2-Linux-Kernel/tree/linux-msft-wsl-6.6.87.2 | GPL-2.0 and component-specific notices |

radar-decode.exe is a custom offline stdin-IQ/JSON wrapper around xng DSP
libraries, not the full xng application. It has no feed/network dependencies.
Rust dependency licenses and xng provenance notices are in vendor/native/Licenses.
OpenDroneID is built with a Windows packing compatibility header; wrapper sources
are included in sources/native. Wi-Fi capture uses the separately installed Npcap;
Npcap binaries are not redistributed in this package.

The Wi-Fi network drivers under `vendor/drivers/alfa` are extracted without
modification from Microsoft Update Catalog updates
`cc3fc658-7aed-49b8-b538-a303d05e818f` (RTL8187 x64) and
`aada4090-82e4-4d18-b8ea-7cbde5c113ba` (RTL8811AU). Their catalog signatures
are retained and validate as Microsoft Windows Hardware Compatibility Publisher.

maps/places.json is an openly supplied derived settlement database, © OpenStreetMap
contributors, distributed under https://opendatacommons.org/licenses/odbl/1-0/ .
Its extraction timestamp, coordinates, names and source object identifiers are
included in the file. It is separate from the EOX image database.

Satellite attribution: EOxCloudless https://cloudless.eox.at by EOX IT Services
GmbH https://eox.at (Contains modified Copernicus Sentinel data 2024).
The local mosaic was cropped, resampled, tiled and JPEG-compressed from the
official WMS service. These derived image tiles remain CC BY-NC-SA 4.0:
https://creativecommons.org/licenses/by-nc-sa/4.0/ . Personal non-commercial use.
Build-time downloader: sources/prepare-satellite.py (requires Pillow).

AIS-catcher's upstream Windows bundle includes its supporting native libraries;
its licenses are retained under vendor/ais/Licenses. VRS supporting DLLs are
unmodified. Binary hashes and origin URLs are recorded in sources/downloads.json.
The source archives supplied alongside this package preserve upstream notices.
No third-party telemetry, sharing or online maps are enabled by this application.

HackRF RX uses `hackrf.dll` supplied with AIS-catcher. HackRF host software:
https://github.com/greatscottgadgets/hackrf . Zadig 2.9 / libwdi 1.5.1 is
distributed unmodified as an optional, user-operated WinUSB installer. Its
executable is signed by Akeo Consulting. Project and licenses:
https://github.com/pbatard/libwdi . Corresponding source is included as
sources/zadig-source.zip.
