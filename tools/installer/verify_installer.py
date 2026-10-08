"""Exercise the actual compiled extractor without starting reception or changing drivers."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / 'dist/RFTrafficMonitor-0.10.2-Setup-win64.exe'

def run(exe, target):
    return subprocess.run([str(exe), '--extract', str(target)], creationflags=subprocess.CREATE_NO_WINDOW).returncode

def main():
    # Keep artifacts in the workspace for inspection; each run gets a fresh directory.
    work = Path(tempfile.mkdtemp(prefix='verify-', dir=ROOT / '.build/installer'))
    target = work / 'Εφαρμογή με κενά'
    assert run(EXE, target) == 0, 'Full extraction failed'
    with zipfile.ZipFile(ROOT / '.build/installer/payload.zip') as archive:
        for member in archive.infolist():
            assert hashlib.sha256((target / member.filename).read_bytes()).digest() == hashlib.sha256(archive.read(member)).digest(), member.filename
    assert json.loads((target / 'config.json').read_text())['rtl_serial'] == ''
    assert not (target / 'data').exists()
    assert not (target / 'vendor/drivers').exists()
    subprocess.run([str(target / 'runtime/python.exe'), '-c', 'import server, rtl_devices, ssl, sqlite3; from PIL import Image; import download_drivers; print("Bundled imports OK")'], check=True)
    helper=target/'vendor/adsb/rtl-probe.exe'
    data=helper.read_bytes()
    pe=struct.unpack_from('<I',data,0x3c)[0]
    assert struct.unpack_from('<H',data,pe+4)[0]==0x14c, 'Discovery helper must be x86'
    inventory=subprocess.run([str(helper),'--list'],capture_output=True,text=True,
                             timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    assert inventory.returncode==0,inventory.stderr
    assert isinstance(json.loads(inventory.stdout),list)
    marker = target / 'keep.txt'
    marker.write_text('preserve')
    assert run(EXE, target) == 1, 'Must refuse overwriting an installation'
    assert marker.read_text() == 'preserve'
    stub = (ROOT / '.build/installer/Setup.exe').read_bytes()
    malicious = work / 'malicious.zip'
    with zipfile.ZipFile(malicious, 'w') as archive: archive.writestr('../outside.txt', 'escape')
    payload = malicious.read_bytes()
    bad = work / 'unsafe.exe'
    bad.write_bytes(stub + payload + b'RFTMSFX1' + struct.pack('<q', len(payload)) + hashlib.sha256(payload).digest())
    assert run(bad, work / 'unsafe-target') == 1
    assert not (work / 'outside.txt').exists()
    bad.write_bytes(stub + payload + b'RFTMSFX1' + struct.pack('<q', len(payload)) + bytes(32))
    assert run(bad, work / 'corrupt-target') == 1
    assert not (work / 'corrupt-target').exists()
    print('PASS: full payload integrity, bundled runtime, neutral configuration, overwrite protection, path traversal, corrupt payload. Test files:', work)

if __name__ == '__main__': main()
