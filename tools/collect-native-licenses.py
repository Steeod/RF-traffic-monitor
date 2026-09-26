from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'app/vendor/native/Licenses'
def collect(base,label):
    for path in base.rglob('*'):
        if path.is_file() and (path.name.upper().startswith(('LICENSE','COPYING','NOTICE')) or path.name=='PROVENANCE.md'):
            target=out/label/path.relative_to(base);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
collect(ROOT/'.build/xng-0.21.0','xng-0.21.0')
collect(ROOT/'.build/opendroneid-core-c-master','OpenDroneID')
for index in (ROOT/'.build/cargo/registry/src').glob('*'):
    for crate in index.iterdir():
        if crate.is_dir():collect(crate,crate.name)
print('License files:',len(list(out.rglob('*.*'))))
