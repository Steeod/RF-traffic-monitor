"""Package the 0.10 -> 0.10.2 update without private settings or generated data."""
from pathlib import Path
import hashlib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
PATCH=('web/rft-icon.png','web/rft-icon.ico','server.py','rtl_devices.py','web/app.js','web/index.html','web/update_logic.js',
       'vendor/adsb/rtl-probe.exe','vendor/adsb/rtlsdr.dll','vendor/adsb/msvcr100.dll','vendor/adsb/pthreadVC2.dll')
SOURCE=('tools/RtlProbe.cs','tools/build-rtl-probe.ps1','tools/build-extra.ps1','tools/package.py','tests/test_rtl_devices.py','tools/bootstrap.py','tools/build-installer.py','tools/package-update.py',
        'tools/installer/Setup.cs','tools/installer/download_drivers.py',
        'tools/installer/verify_installer.py','tools/installer/README.md',
        'tests/test_update_logic.js','UPDATE-0.10.2.md')

def main():
    OUT.mkdir(exist_ok=True)
    patch=OUT/'RFTrafficMonitor-0.10.2-update.zip'
    with zipfile.ZipFile(patch,'w',zipfile.ZIP_DEFLATED,strict_timestamps=False) as z:
        for name in PATCH:z.write(ROOT/'app'/name,name)
        z.write(ROOT/'UPDATE-0.10.2.md','UPDATE-0.10.2.md')
        z.write(ROOT/'app/vendor/adsb/rtl-sdr-copying.txt','vendor/adsb/rtl-sdr-copying.txt')
        z.write(ROOT/'tools/RtlProbe.cs','sources/RtlProbe.cs')
        z.write(ROOT/'tools/build-rtl-probe.ps1','sources/build-rtl-probe.ps1')
        z.write(ROOT/'downloads/rtl-source.zip','sources/rtl-source.zip')
    source=OUT/'RFTrafficMonitor-0.10.2-source-update.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for name in PATCH:
            if not name.startswith('vendor/'):z.write(ROOT/'app'/name,'app/'+name)
        for name in SOURCE:z.write(ROOT/name,name)
    assets=[patch,source,OUT/'RFTrafficMonitor-0.10.2-Setup-win64.exe']
    sums=[]
    for path in assets:
        with path.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
        sums.append(digest+'  '+path.name)
        print(path.name,path.stat().st_size)
    (OUT/'SHA256SUMS-0.10.2.txt').write_text('\n'.join(sums)+'\n')

if __name__=='__main__':main()
