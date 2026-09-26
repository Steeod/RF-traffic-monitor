# Third-party credits and code origins

Reviewed 2026-09-26 from the local source, build scripts and upstream notices.
These credits distinguish libraries actually used from reference projects.
Links do not replace the license texts and corresponding source required for
redistributed components. Portable-package notices also live in
[app/THIRD-PARTY.md](app/THIRD-PARTY.md).

## Code and runtime dependencies

| Project | Use here | License / evidence |
|---|---|---|
| [Virtual Radar Server](https://github.com/vradarserver/vrs) 2.4.4 | `app/VrsBridge.cs` calls its aircraft parsing libraries | BSD-3-Clause; Andrew Whewell; retain supporting DLL notices too |
| [dump1090, MalcolmRobb fork](https://github.com/MalcolmRobb/dump1090) 1.10.3010.14 | Separate ADS-B decoder executable | BSD-2-Clause main code, Salvatore Sanfilippo and contributors; inspect bundled library notices |
| [RTL-SDR Blog](https://github.com/rtlsdrblog/rtl-sdr-blog/tree/V1.4.0) V1.4.0 | RTL-SDR native USB receiver library | GPL v2; preserve file-level terms and corresponding source |
| [AIS-catcher](https://github.com/jvde-github/AIS-catcher/tree/v0.70) v0.70 | Separate AIS decoder; bundle also supplies native libraries | GPL v3; dependencies have their own notices |
| [HackRF](https://github.com/greatscottgadgets/hackrf) | `app/hackrf_worker.py` calls the AIS-catcher bundle's `hackrf.dll` | Audit the exact bundled libhackrf version and license, including USB dependencies, before release |
| [xng](https://github.com/airframesio/xng/tree/v0.21.0) 0.21.0 | `app/native/src/main.rs` links ACARS, VDL2, HFDL and sonde crates | MIT OR Apache-2.0; Kevin Elliott and xng contributors; exact dependency graph in `app/native/Cargo.lock` |
| [libacars](https://github.com/szpajder/libacars) | Indirect code origin: xng-acars explicitly ports libacars parsing/reassembly code | MIT; upstream provenance credits Tomasz Lemiech, 2018–2023; retain the exact upstream copyright/license notices |
| [OpenDroneID core C](https://github.com/opendroneid/opendroneid-core-c) | `app/native/rid_decode.c` wraps Basic ID and Location decoding; `odid_compat.h` adapts MSVC packing | Apache-2.0; master archive is not an immutable revision |
| [Python](https://www.python.org/downloads/release/python-31210/) 3.12.10 | Optional embedded Windows interpreter | PSF license and bundled notices |
| [Zadig / libwdi](https://github.com/pbatard/libwdi/tree/v1.5.1) | Optional external WinUSB installer, Zadig 2.9 | Preserve the executable's applicable notices; libwdi LGPL and Zadig GPL terms must not be flattened into one license |
| [Npcap](https://npcap.com/) | Optional separately installed capture library | Npcap terms; binaries are not redistributed |
| [Pillow](https://github.com/python-pillow/Pillow) | Build-time satellite image conversion | HPND; separately installed, not vendored |

Rust dependencies such as serde, serde_json, num-complex and their transitive
dependencies are pinned by Cargo.lock. `tools/collect-native-licenses.py` collects
license files from the local Cargo registry and xng/OpenDroneID sources for a
binary package. Its output must be checked against the actual build graph; the
script alone is not proof of complete notices.

## Reference projects identified in xng provenance

The preserved [xng provenance notices](third_party/xng/crates/) give the detailed
distinction between ports, protocol references and output comparisons:

- **libacars** is explicitly a ported code origin, not merely an inspiration.
- [acarsdec](https://github.com/TLeconte/acarsdec) is cited for syndrome-table
  behavior and test values in the ACARS notice.
- [dumpvdl2](https://github.com/szpajder/dumpvdl2) and
  [dumphfdl](https://github.com/szpajder/dumphfdl) are described by xng as
  protocol/output references; that description is an upstream claim, not a
  fresh independent code-origin audit.
- [rs1729/RS](https://github.com/rs1729/RS) supplies RS41 reference frame facts,
  published vectors and decoder comparisons according to xng's sonde notice.

The local `.build/DroneCMD-main` and `.build/receiver-android-master` directories
are outside the publication set. Their presence does not establish that their
code was copied into this project; no such attribution marker was found in the
application source. Confirm any undocumented copying before public release.

## Optional WSL and driver components

| Project | Version/source used by downloader | Release consideration |
|---|---|---|
| [usbipd-win](https://github.com/dorssel/usbipd-win/tree/v5.3.0) | 5.3.0 MSI | GPL-3.0; current helper downloads the MSI without its corresponding source |
| [aircrack-ng/rtl8812au](https://github.com/aircrack-ng/rtl8812au/tree/v5.6.4.2) | Branch `v5.6.4.2` | GPL v2 family; retain exact archive notices and pin the commit |
| [lwfinger/rtw88](https://github.com/lwfinger/rtw88) | `master` archive | Retain code and any firmware-specific terms; pin the commit |
| [WSL2 Linux kernel](https://github.com/microsoft/WSL2-Linux-Kernel/tree/linux-msft-wsl-6.6.87.2) | `linux-msft-wsl-6.6.87.2` source | GPL-2.0 with component-specific notices; preserve `COPYING` and `LICENSES/` |
| Realtek Windows drivers via Microsoft Update Catalog | RTL8187 x64: `cc3fc658-7aed-49b8-b538-a303d05e818f`; RTL8811AU: `aada4090-82e4-4d18-b8ea-7cbde5c113ba` | Redistribution permission is not established by a Microsoft signature; omit from public packages until terms are verified |

## Maps and test data

- [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/): public
  domain land polygons, cropped locally by `tools/prepare-map.py` into the
  Git-ignored `app/maps/land.json`.
- © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright):
  the Git-ignored `app/maps/places.json` is a locally generated settlement database under
  [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Extraction code is
  `tools/prepare-places.py`; source object IDs and extraction metadata are retained.
- Optional satellite tiles: EOxCloudless https://cloudless.eox.at by
  EOX IT Services GmbH https://eox.at (Contains modified Copernicus Sentinel data 2024).
  Cropped, resampled, tiled and JPEG-compressed. The imagery remains
  [CC BY-NC-SA 4.0](https://cloudless.eox.at/license-non-commercial), with attribution
  and non-commercial/share-alike conditions. It is excluded from Git.
- The locally retained, Git-ignored `tests/fixtures/rs41.json` contains xng
  0.21.0 decoder output for serial
  N3920808. This matches the sonde sample identified in xng's bench README as
  the [projecthorus/radiosonde_auto_rx](https://github.com/projecthorus/radiosonde_auto_rx)
  decoder-performance capture (Adelaide, 2019-02-10), distributed by xng through
  [bench-fixtures-v1](https://github.com/airframesio/xng/releases/tag/bench-fixtures-v1).
  The match is provenance evidence, not a confirmed license for that derived
  fixture. It is excluded from publication unless the original sample terms
  are confirmed. The published test uses a project-authored synthetic message.
  Raw IQ recordings under `downloads/fixtures/` are excluded from Git.

No root project license overrides any of these component or data terms.
