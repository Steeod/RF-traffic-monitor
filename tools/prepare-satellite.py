"""Build the configurable EOX offline map using the application downloader."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    config_path = ROOT / 'app/config.json'
    defaults = json.loads(config_path.read_text('utf-8')) if config_path.exists() else {}
    parser = argparse.ArgumentParser()
    parser.add_argument('--latitude', type=float, default=defaults.get('map_latitude'))
    parser.add_argument('--longitude', type=float, default=defaults.get('map_longitude'))
    parser.add_argument('--radius-km', type=int, default=200)
    args = parser.parse_args()
    if args.latitude is None or args.longitude is None:
        parser.error('provide --latitude and --longitude or create app/config.json with setup.ps1')
    subprocess.run([sys.executable, str(ROOT / 'app/map_downloader.py'),
                    str(args.latitude), str(args.longitude), str(args.radius_km)], check=True)


if __name__ == '__main__':
    main()
