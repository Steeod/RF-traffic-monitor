"""Download pinned driver packages beside the installed application; never install them."""
import contextlib
from pathlib import Path
import subprocess
import traceback
import installer_dependencies as deps

ROOT = Path(__file__).resolve().parent

def main():
    deps.ROOT = ROOT
    deps.DOWNLOADS = ROOT / 'vendor' / 'drivers'
    deps.DOWNLOADS.mkdir(parents=True, exist_ok=True)
    name = 'zadig-2.9.exe'
    deps.download(name, *deps.ARTIFACTS[name])
    for name, model in [('rtl8187-microsoft.cab', 'awus036h'), ('rtl8811au-microsoft.cab', 'awus036acs')]:
        update, expected = deps.CATALOG_DRIVERS[name]
        archive = deps.DOWNLOADS / name
        if not archive.exists() or deps.digest(archive) != expected:
            deps.download(name, deps.catalog_url(update), expected)
        target = deps.DOWNLOADS / 'alfa' / model
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run(['expand.exe', '-F:*', str(archive), str(target)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('Driver packages downloaded and verified. USB: run Zadig and choose your receiver. Alfa: use Windows Device Manager to install the matching INF from this folder.')

if __name__ == '__main__':
    with (ROOT / 'driver-download.log').open('w', encoding='utf-8') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                main()
            except Exception:
                traceback.print_exc()
                raise SystemExit(1)
