import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
exe=ROOT/'app/vendor/native/radar-decode.exe'
for mode,file,rate,frequency,fmt in [
    ('acars','acars_100k.cs16',100000,131550000,'i16'),
    ('vdl2','vdl2_105k_conj.s16',105000,136975000,'i16'),
    ('hfdl','hfdl_48k.cs16',48000,21931000,'i16'),
    ('sonde','sonde_96k.cf32',96000,404000000,'f32')]:
    with (ROOT/'downloads/fixtures'/file).open('rb') as source:
        r=subprocess.run([str(exe),mode,str(rate),str(frequency),str(frequency),fmt],stdin=source,capture_output=True,timeout=90)
    if r.returncode:raise RuntimeError(r.stderr.decode())
    rows=[json.loads(line) for line in r.stdout.splitlines()]
    (ROOT/'.build'/f'{mode}-decoded.json').write_text(json.dumps(rows),'utf-8')
    print(mode,len(rows),'first body:',json.dumps(rows[0]['body'])[:400] if rows else 'NONE',flush=True)
    assert len(rows)>0,mode
