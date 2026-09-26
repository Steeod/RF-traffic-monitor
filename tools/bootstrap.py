"""Download, verify and lay out the portable RF Traffic Monitor dependencies."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = ROOT / 'downloads'

ARTIFACTS = {
    'python.zip': ('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip', '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3'),
    'VirtualRadar.tar.gz': ('https://www.virtualradarserver.co.uk/Files/VirtualRadar.tar.gz', 'b3d956b4e049c97b4fec93452ac5ad14225b3e9b732ed62aeceb1e6cf5b24344'),
    'AIS-catcher.x64.zip': ('https://github.com/jvde-github/AIS-catcher/releases/download/v0.70/AIS-catcher.x64.zip', 'e6dca80fd1e09e4ec9a3b676a15c386167e9197d9bffc91bff3d88750227ceef'),
    'dump1090.zip': ('https://raw.githubusercontent.com/MalcolmRobb/dump1090/master/dump1090-win.1.10.3010.14.zip', '583ff843b2fe39212eb4d3ebd7e3721ffcc0ee1f3bc7be4dc0507d2350367834'),
    'land.geojson': ('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_land.geojson', '1ac90796408bc6ad6911d69448485d3c4dbf2190370080368a09976e1c9f7416'),
    'rtl-v4.zip': ('https://github.com/rtlsdrblog/rtl-sdr-blog/releases/download/V1.4.0/Release.zip', '7ef33f1304647f65e5e0fde43637a73d54f076e91e651a3cecc4f55a17fd9815'),
    'zadig-2.9.exe': ('https://github.com/pbatard/libwdi/releases/download/v1.5.1/zadig-2.9.exe', '4ecaa95df3da3621486a043aef8b3050b8bafe7c901402871e816229ef82039b'),
    'rtl-source.zip': ('https://codeload.github.com/rtlsdrblog/rtl-sdr-blog/zip/aed0ea19f3a273370a13c9009b96313c75d54c7b', '77cc07ade5560700f9e79b868bb09275ccd84721d8a670efe6af9d6eb8c90b2d'),
    'ais-source.zip': ('https://github.com/jvde-github/AIS-catcher/archive/refs/tags/v0.70.zip', '7ae0ea34b5f8589537c298b6a4bef736ae2558899212a6e48923ec28c9c51eba'),
    'dump1090-source.zip': ('https://github.com/MalcolmRobb/dump1090/archive/refs/heads/master.zip', '41e66e19c5d811004f7c2c0071681360146e2c924bfeda128575066124c2245c'),
    'vrs-source.zip': ('https://codeload.github.com/vradarserver/vrs/zip/5caf149a5077c79eeb589a1b4f8c61f3c9081b00', '2462f85c2f2c8b72595f770e0592d9186ca40cf60f53c9dd64eee1e1e3235780'),
    'xng-source.zip': ('https://github.com/airframesio/xng/archive/refs/tags/v0.21.0.zip', 'f8ac06e234ba682a2999b818ec164041cb0ce41b1fbaf7bd70d0591257a397f3'),
    'odid-source.zip': ('https://github.com/opendroneid/opendroneid-core-c/archive/refs/heads/master.zip', 'c1aa5abcfa0eddfb2fcb8ba4604c33b9f2cf78a3daa67df1576ae8edd42d8caf'),
    'zadig-source.zip': ('https://github.com/pbatard/libwdi/archive/refs/tags/v1.5.1.zip', '746547aaf927cae44c75512d763941805928427f4ba4df3dbb40c3f7f561821e'),
}

CATALOG_DRIVERS = {
    'rtl8187-microsoft.cab': ('cc3fc658-7aed-49b8-b538-a303d05e818f', '088dd97b752c2165877b69f0edabfb9f3d20c49bc6e8a90254b1b514a89bbb28'),
    'rtl8811au-microsoft.cab': ('aada4090-82e4-4d18-b8ea-7cbde5c113ba', '8887736ae3e2fd498a1e376a06db8c67f0dbb1ad4934ef2441e67f13f9249915'),
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def catalog_url(update_id: str) -> str:
    payload = json.dumps([{'size': 0, 'languages': '', 'uidInfo': update_id, 'updateID': update_id}])
    body = urllib.parse.urlencode({'updateIDs': payload}).encode()
    request = urllib.request.Request('https://www.catalog.update.microsoft.com/DownloadDialog.aspx', data=body,
                                     headers={'User-Agent': 'RFTrafficMonitor/0.10 bootstrap'})
    page = urllib.request.urlopen(request, timeout=90).read().decode('utf-8', 'replace')
    match = re.search(r"files\[\d+\]\.url\s*=\s*'([^']+\.cab)'", page, re.I)
    if not match:
        raise RuntimeError(f'Microsoft Update Catalog returned no CAB for {update_id}')
    return match.group(1)


def download(name: str, url: str, expected: str) -> Path:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    target = DOWNLOADS / name
    seed = ROOT / 'app/vendor/drivers' / name
    if not target.exists() and seed.exists() and digest(seed).lower() == expected.lower():
        shutil.copy2(seed, target)
    if target.exists() and digest(target).lower() == expected.lower():
        print(f'[cached] {name}')
        return target
    target.unlink(missing_ok=True)
    temporary = target.with_suffix(target.suffix + '.part')
    temporary.unlink(missing_ok=True)
    print(f'[download] {name}')
    request = urllib.request.Request(url, headers={'User-Agent': 'RFTrafficMonitor/0.10 bootstrap'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=180) as response, temporary.open('wb') as output:
                shutil.copyfileobj(response, output, 1024 * 1024)
            break
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    actual = digest(temporary)
    if actual.lower() != expected.lower():
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f'SHA-256 mismatch for {name}: {actual}')
    temporary.replace(target)
    return target


def safe_zip(source: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(source) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f'Unsafe ZIP path: {member.filename}')
        archive.extractall(destination)


def safe_tar(source: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(source) as archive:
        archive.extractall(destination, filter='data')


def reset_directory(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def configure_embedded_python(runtime: Path):
    """Allow the embedded interpreter to import modules from the app directory."""
    path_files = list(runtime.glob('python*._pth'))
    if len(path_files) != 1:
        raise RuntimeError(f'Expected one embedded Python _pth file, found {len(path_files)}')
    path_file = path_files[0]
    lines = path_file.read_text('utf-8').splitlines()
    if '..' not in lines:
        insert_at = lines.index('.') + 1 if '.' in lines else len(lines)
        lines.insert(insert_at, '..')
    path_file.write_text('\n'.join(lines) + '\n', 'utf-8')


def dependencies():
    records = []
    for name, (url, expected) in ARTIFACTS.items():
        path = download(name, url, expected)
        records.append({'file': name, 'url': url, 'sha256': digest(path)})
    for name, (update_id, expected) in CATALOG_DRIVERS.items():
        existing = DOWNLOADS / name
        url = 'Microsoft Update Catalog update ' + update_id
        if not existing.exists() or digest(existing).lower() != expected:
            resolved = catalog_url(update_id)
            download(name, resolved, expected)
            url = resolved
        records.append({'file': name, 'url': url, 'sha256': digest(DOWNLOADS / name),
                        'catalog_update_id': update_id})
    (DOWNLOADS / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n', 'utf-8')


def materialize():
    runtime = ROOT / 'app/runtime'
    reset_directory(runtime)
    safe_zip(DOWNLOADS / 'python.zip', runtime)
    configure_embedded_python(runtime)

    ais = ROOT / 'app/vendor/ais'
    reset_directory(ais)
    safe_zip(DOWNLOADS / 'AIS-catcher.x64.zip', ais)

    adsb = ROOT / 'app/vendor/adsb'
    reset_directory(adsb)
    safe_zip(DOWNLOADS / 'dump1090.zip', adsb)

    vrs = ROOT / 'app/vendor/vrs'
    reset_directory(vrs)
    safe_tar(DOWNLOADS / 'VirtualRadar.tar.gz', vrs)

    rtl = DOWNLOADS / 'rtl-v4'
    reset_directory(rtl)
    safe_zip(DOWNLOADS / 'rtl-v4.zip', rtl)
    native = ROOT / 'app/vendor/native'
    native.mkdir(parents=True, exist_ok=True)
    for library in (rtl / 'x64').glob('*.dll'):
        shutil.copy2(library, native / library.name)

    drivers = ROOT / 'app/vendor/drivers'
    drivers.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DOWNLOADS / 'zadig-2.9.exe', drivers / 'zadig-2.9.exe')
    for name, destination in (('rtl8187-microsoft.cab', 'awus036h'),
                              ('rtl8811au-microsoft.cab', 'awus036acs')):
        target = drivers / 'alfa' / destination
        reset_directory(target)
        subprocess.run(['expand.exe', '-F:*', str(DOWNLOADS / name), str(target)], check=True,
                       stdout=subprocess.DEVNULL)

    build = ROOT / '.build'
    build.mkdir(exist_ok=True)
    for archive in ('xng-source.zip', 'odid-source.zip'):
        safe_zip(DOWNLOADS / archive, build)


def configure(station_name: str, latitude: float, longitude: float,
              wifi_support: str = 'none', wifi_adapter: str = 'other', receiver_type: str = 'rtl'):
    template = json.loads((ROOT / 'app/config.example.json').read_text('utf-8'))
    template.update(station_name=station_name, latitude=latitude, longitude=longitude,
                    map_latitude=latitude, map_longitude=longitude)
    template.update(wifi_enabled=wifi_support != 'none', receiver_type=receiver_type,
                    wifi_backend='wsl' if wifi_support == 'wsl' else 'windows',
                    wifi_model={'awus036h': 'awus036h', 'awus036acs': 'awus036acs'}.get(wifi_adapter, 'other'),
                    wifi_adapter='')
    if receiver_type == 'wifi':
        template['scan']={'adsb':False,'ais':False}
    (ROOT / 'app/config.json').write_text(json.dumps(template, indent=2, ensure_ascii=False) + '\n', 'utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('dependencies', 'materialize', 'configure', 'all'))
    parser.add_argument('--station-name', default='My receiving station')
    parser.add_argument('--latitude', type=float)
    parser.add_argument('--longitude', type=float)
    parser.add_argument('--receiver-type', choices=('rtl', 'hackrf', 'wifi'), default='rtl')
    parser.add_argument('--wifi-support', choices=('none', 'windows', 'wsl'), default='none')
    parser.add_argument('--wifi-adapter', choices=('none', 'awus036h', 'awus036acs', 'other'), default='other')
    args = parser.parse_args()
    if args.stage in ('dependencies', 'all'):
        dependencies()
    if args.stage in ('materialize', 'all'):
        materialize()
    if args.stage in ('configure', 'all'):
        if args.latitude is None or args.longitude is None:
            parser.error('configure requires --latitude and --longitude')
        configure(args.station_name, args.latitude, args.longitude, args.wifi_support, args.wifi_adapter, args.receiver_type)


if __name__ == '__main__':
    main()
