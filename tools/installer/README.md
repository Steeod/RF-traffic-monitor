# Self-extracting Windows setup

Run `python tools/build-installer.py` from a provisioned checkout on Windows.
Output: `dist/RFTrafficMonitor-0.10.3-Setup-win64.exe` and its SHA-256 file.
The build uses the Windows .NET Framework C# compiler, current `app/` files,
and the existing portable bundle's source archives and optional WSL bundle.
No extra installer toolchain is required. Target: 64-bit Windows 10/11.

Double-click the EXE, use the RFTrafficMonitor subfolder beside Setup (the default) or choose another destination, and press Install. It verifies
and extracts its embedded payload and, by default, downloads pinned Zadig and
Alfa AWUS036H/AWUS036ACS packages into `vendor/drivers` under that folder.
All downloaded bytes must match the SHA-256 values from `tools/bootstrap.py`.
The application runtime and decoders are embedded; users do not need Python,
Rust, or Visual Studio. Existing maps are included; choose your station, receiver and map radius in the first-run setup. Country, city or island
search fills coordinates when a result is selected. Receiver configuration is reset
to `config.example.json`; logs and captures are excluded.

Launch the installed app with `Start.cmd`. Failed downloads leave the app
available and can be retried with `Download Drivers.cmd`; details are written
to `driver-download.log`. Installation checks all application paths before extracting and refuses
collisions. Unrelated files and the Setup executable may remain in the destination. There are no registry or
PATH changes, services, or automatic hardware-driver changes.

USB WinUSB installation still requires choosing the actual receiver in Zadig.
For an Alfa adapter, install its matching INF through Windows Device Manager.
Optional Npcap and WSL operating-system setup remain separate, as documented
in the application; this EXE does not silently enable Windows features.

The EXE is unsigned. It is a local test build; the existing public-release
requirements in `PUBLISHING.md` still apply to bundled third-party components.
Do not Authenticode-sign this overlay format without changing the payload
locator: its trailer is read relative to EOF.

The displayed path is the final application folder. Files are not scattered
beside Setup. `--extract-default` tests the same default subfolder path without
downloading drivers.

For automated extraction testing, use `Setup.exe --extract "EMPTY_FOLDER"`.
This mode never downloads drivers or starts the application. Exit code 0 means
success; errors return 1 and are recorded at `EMPTY_FOLDER.error.txt`.
