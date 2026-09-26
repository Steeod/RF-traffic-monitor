# Rebuilding the additional native decoders

This is not required to run the application because the portable release includes
the executables under `vendor/native`. Development builds use Rust 1.98.1 MSVC
x64, Visual Studio 2022 C++ Build Tools, and Windows SDK 10.0.26100.0.

From the root of an extracted portable package:

```powershell
New-Item -ItemType Directory -Force .build
Expand-Archive sources/xng-source.zip .build -Force
Expand-Archive sources/odid-source.zip .build -Force
cargo build --release --locked --manifest-path sources/native/Cargo.toml
powershell -ExecutionPolicy Bypass -File sources/build-extra.ps1
```

The first Cargo run downloads dependencies from crates.io. The resulting
application runs offline. Exact versions are recorded in `Cargo.lock`.
Upstream archive hashes are in `hashes.json`, origins are in `downloads.json`,
and licenses are included under `vendor/native/Licenses`.

If Visual Studio is installed elsewhere, adjust the `vs` variable in
`build-extra.ps1`. Keep the bundled RTL-SDR libraries in `vendor/native`.

In the source repository, Cargo uses `app/native/Cargo.toml` and the build script
is `tools/build-extra.ps1`. `radar-decode` links only the xng DSP decoders.
`rid_decode.dll` uses OpenDroneID core C. `wifi_rid_worker.py` reads Wi-Fi Beacon
Information Elements through the Windows WLAN API or, optionally, raw 802.11
frames through Npcap and a compatible monitor-mode driver.
