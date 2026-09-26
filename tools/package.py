"""Build a relocatable folder/ZIP; omit upstream UIs and feeder executables."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
if not (ROOT/'app/maps/satellite.json').exists():
    raise RuntimeError('Complete tools/prepare-satellite.py before packaging')
if not (ROOT/'app/maps/places.json').exists():
    raise RuntimeError('Complete tools/prepare-places.py before packaging')
for name in ('ais','rtl','dump1090','vrs','xng','odid','zadig'):
    if not (ROOT/'downloads'/f'{name}-source.zip').exists():
        raise RuntimeError(f'Missing {name} upstream source archive')
OUT=ROOT/'dist/RFTrafficMonitor'
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True,exist_ok=True)

def copy(path, dest=None):
    target=OUT/(dest or path)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'app'/path,target)

for name in ('Start.cmd','server.py','model.py','protocols.py','remote_id.py','rtl_worker.py','hackrf_worker.py','wifi_rid_worker.py','wsl_wifi.py','map_downloader.py','config.json','VrsBridge.cs','THIRD-PARTY.md'):
    if name=='config.json' and (OUT/name).exists():continue
    copy(name)
for name in ('LICENSE','README.md','LICENSE-STATUS.md','THIRD-PARTY.md'):
    shutil.copy2(ROOT/name,OUT/name)
for folder in ('web','maps','runtime','wsl'):
    for f in (ROOT/'app'/folder).rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:
            copy(f.relative_to(ROOT/'app'))
for folder in ('ais','adsb','vrs','native','drivers'):
    for f in (ROOT/'app/vendor'/folder).rglob('*'):
        if not f.is_file():continue
        allowed=(f.suffix.lower() in ('.dll','.inf','.cat','.sys') or f.name in ('AIS-catcher.exe','dump1090.exe','VrsBridge.exe','radar-decode.exe','zadig-2.9.exe')
                 or 'Licenses' in f.parts or f.name.lower() in ('readme.md','readme.txt','license.txt','rtl-sdr-copying.txt'))
        if allowed:copy(f.relative_to(ROOT/'app'))
bundle=ROOT/'downloads/wsl-bundle'
(OUT/'vendor/wsl-bundle').mkdir(parents=True,exist_ok=True)
for f in bundle.glob('*'):
    if f.is_file():shutil.copy2(f,OUT/'vendor/wsl-bundle'/f.name)
(OUT/'sources').mkdir(exist_ok=True)
manifest=[]
for f in (ROOT/'downloads').glob('*'):
    if f.is_file() and f.suffix in ('.zip','.gz'):
        manifest.append({'file':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
for f in (ROOT/'downloads').glob('*-source.zip'):
    if f.name=='odid-android-source.zip':continue # Reference only, not used in binary.
    shutil.copy2(f,OUT/'sources'/f.name)
if (ROOT/'downloads/manifest.json').exists():
    origins=json.loads((ROOT/'downloads/manifest.json').read_text('utf-8'))
    extra={
        'rtl-v4.zip':'https://github.com/rtlsdrblog/rtl-sdr-blog/releases/download/V1.4.0/Release.zip',
        'rtl-source.zip':'https://codeload.github.com/rtlsdrblog/rtl-sdr-blog/zip/aed0ea19f3a273370a13c9009b96313c75d54c7b',
        'ais-source.zip':'https://github.com/jvde-github/AIS-catcher/archive/refs/tags/v0.70.zip',
        'dump1090-source.zip':'https://github.com/MalcolmRobb/dump1090/archive/refs/heads/master.zip',
        'vrs-source.zip':'https://codeload.github.com/vradarserver/vrs/zip/5caf149a5077c79eeb589a1b4f8c61f3c9081b00',
        'xng-source.zip':'https://github.com/airframesio/xng/archive/refs/tags/v0.21.0.zip',
        'odid-source.zip':'https://github.com/opendroneid/opendroneid-core-c/archive/refs/heads/master.zip',
        'zadig-source.zip':'https://github.com/pbatard/libwdi/archive/refs/tags/v1.5.1.zip'}
    for name,url in extra.items():
        f=ROOT/'downloads'/name
        if f.exists():origins.append(dict(file=name,url=url,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
    (OUT/'sources/downloads.json').write_text(json.dumps(origins,indent=2),'utf-8')
(OUT/'sources/hashes.json').write_text(json.dumps(manifest,indent=2),'utf-8')
shutil.copy2(ROOT/'tools/build-bridge.ps1',OUT/'sources/build-bridge.ps1')
shutil.copy2(ROOT/'tools/prepare-satellite.py',OUT/'sources/prepare-satellite.py')
shutil.copy2(ROOT/'tools/prepare-places.py',OUT/'sources/prepare-places.py')
for f in (ROOT/'app/native').rglob('*'):
    if f.is_file() and 'target' not in f.relative_to(ROOT/'app/native').parts:
        target=OUT/'sources/native'/f.relative_to(ROOT/'app/native');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
shutil.copy2(ROOT/'tools/build-extra.ps1',OUT/'sources/build-extra.ps1')
shutil.copy2(ROOT/'tools/BUILD.md',OUT/'sources/BUILD.md')
archive=ROOT/'dist/RFTrafficMonitor-0.10-win64.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False) as z:
    for f in OUT.rglob('*'):
        if f.is_file() and 'data' not in f.relative_to(OUT).parts and '__pycache__' not in f.parts:
            z.write(f,Path('RFTrafficMonitor')/f.relative_to(OUT))
print(str(archive),archive.stat().st_size)
