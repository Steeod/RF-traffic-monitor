"""Download redistributable WSL helper/driver sources without installing them."""
import hashlib,json,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'downloads/wsl-bundle';OUT.mkdir(parents=True,exist_ok=True)
FILES={
 'usbipd-win_5.3.0_x64.msi':('https://github.com/dorssel/usbipd-win/releases/download/v5.3.0/usbipd-win_5.3.0_x64.msi','1c984914aec944de19b64eff232421439629699f8138e3ddc29301175bc6d938'),
 'rtl8812au-v5.6.4.2.zip':('https://github.com/aircrack-ng/rtl8812au/archive/refs/heads/v5.6.4.2.zip','42239eeda457345029690dd45c8a668b22eaad685e697f2376c26da15d1b3d8e'),
 'rtw88-master.zip':('https://github.com/lwfinger/rtw88/archive/refs/heads/master.zip','92f50e689e7b0022ea11281203f9af0f859caf3a7e5c0a4ffe21c67cefb755df'),
 'WSL2-Linux-Kernel-6.6.87.2.zip':('https://github.com/microsoft/WSL2-Linux-Kernel/archive/refs/tags/linux-msft-wsl-6.6.87.2.zip','17d7567d28e23992bfc7e0fc60fff7742710fc309cf67a847f9ede56c435bb8a')}
manifest=[]
for name,(url,expected) in FILES.items():
    path=OUT/name
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        path.unlink()
    if not path.exists():
        print('Downloading',name,flush=True)
        request=urllib.request.Request(url,headers={'User-Agent':'RFTrafficMonitor portable bundle builder'})
        with urllib.request.urlopen(request,timeout=180) as response,path.open('wb') as target:
            while block:=response.read(1024*1024):target.write(block)
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual!=expected:raise RuntimeError(f'SHA-256 mismatch for {name}: {actual}')
    manifest.append({'file':name,'url':url,'size':path.stat().st_size,'sha256':actual})
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
print(json.dumps(manifest,indent=2))
