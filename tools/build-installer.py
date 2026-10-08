"""Build one Windows self-extracting EXE from provisioned local app dependencies."""
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.build' / 'installer'

def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    required = ['runtime/python.exe', 'vendor/native/radar-decode.exe', 'vendor/ais/AIS-catcher.exe', 'vendor/adsb/dump1090.exe', 'vendor/vrs/VrsBridge.exe']
    for name in required:
        if not (ROOT / 'app' / name).is_file():
            raise RuntimeError('Missing dependency: ' + name + '; provision the app first.')
    subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/build-rtl-probe.ps1')],check=True)
    files = {}
    for path in (ROOT / 'app').rglob('*'):
        relative = path.relative_to(ROOT / 'app')
        if not path.is_file() or any(part in ('__pycache__', 'data', 'target') for part in relative.parts[:-1]) or relative.parts[0] == 'native':
            continue
        if relative.parts[0] not in ('runtime', 'vendor', 'web', 'maps', 'wsl') and len(relative.parts) > 1:
            continue
        if relative.parts[:2] == ('vendor', 'drivers') or relative.name in ('config.json', 'config.example.json') or path.suffix in ('.log', '.pyc'):
            continue
        files[relative.as_posix()] = path
    for path in (ROOT / 'dist/RFTrafficMonitor/vendor/wsl-bundle').glob('*'):
        if path.is_file(): files['vendor/wsl-bundle/' + path.name] = path
    for path in (ROOT / 'dist/RFTrafficMonitor/sources').rglob('*'):
        if path.is_file(): files['sources/' + path.relative_to(ROOT / 'dist/RFTrafficMonitor/sources').as_posix()] = path
    for name in ('LICENSE', 'LICENSE-STATUS.md', 'THIRD-PARTY.md', 'README.md'):
        files[name] = ROOT / name
    files['sources/RtlProbe.cs'] = ROOT/'tools/RtlProbe.cs'
    files['sources/build-rtl-probe.ps1'] = ROOT/'tools/build-rtl-probe.ps1'
    files['config.json'] = ROOT / 'app/config.example.json'
    files['download_drivers.py'] = ROOT / 'tools/installer/download_drivers.py'
    files['installer_dependencies.py'] = ROOT / 'tools/bootstrap.py'
    payload = BUILD / 'payload.zip'
    with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False) as archive:
        for name, path in sorted(files.items()): archive.write(path, name)
        archive.writestr('Download Drivers.cmd', '@echo off\r\ncd /d "%~dp0"\r\n"%~dp0runtime\\python.exe" "%~dp0download_drivers.py"\r\ntype driver-download.log\r\npause\r\n')
        if 'maps/land.json' not in files: archive.writestr('maps/land.json', '{"polygons":[]}')
        if 'maps/places.json' not in files: archive.writestr('maps/places.json', '{"places":[]}')
    csc = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    stub = BUILD / 'Setup.exe'
    subprocess.run([str(csc), '/nologo', '/target:winexe', '/platform:x64', '/optimize+', '/win32icon:' + str(ROOT/'app/web/rft-icon.ico'), '/out:' + str(stub), '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll', '/r:System.IO.Compression.dll', str(ROOT / 'tools/installer/Setup.cs')], check=True)
    output = ROOT / 'dist/RFTrafficMonitor-0.10.2-Setup-win64.exe'
    output.parent.mkdir(exist_ok=True)
    digest = hashlib.sha256()
    with output.open('wb') as dest:
        with stub.open('rb') as source: shutil.copyfileobj(source, dest)
        with payload.open('rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(block); dest.write(block)
        dest.write(b'RFTMSFX1' + struct.pack('<q', payload.stat().st_size) + digest.digest())
    with output.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    output.with_suffix('.exe.sha256').write_text(checksum + '  ' + output.name + '\n')
    print(str(output), output.stat().st_size, checksum)

if __name__ == '__main__': main()
