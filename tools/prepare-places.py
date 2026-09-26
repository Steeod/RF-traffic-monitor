"""Download an OSM settlement extract around a configurable station."""
import argparse
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('latitude', type=float)
    parser.add_argument('longitude', type=float)
    parser.add_argument('--radius-km', type=int, default=200)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--input', type=Path, help='Use an existing Overpass JSON response')
    args = parser.parse_args()
    if not -85 <= args.latitude <= 85 or not -180 <= args.longitude <= 180:
        raise ValueError('Latitude must be -85..85 and longitude -180..180')
    margin = max(220.0, args.radius_km * 1.1)
    dy = margin / 111.195
    dx = margin / (111.195 * max(0.15, math.cos(math.radians(args.latitude))))
    bounds = [max(-180, args.longitude - dx), max(-85, args.latitude - dy),
              min(180, args.longitude + dx), min(85, args.latitude + dy)]
    west, south, east, north = bounds
    query = ('[out:json][timeout:120];'
             'node["place"~"^(city|town|village|hamlet|suburb|neighbourhood)$"]'
             f'({south},{west},{north},{east});out body;')
    cache = ROOT / 'downloads' / f'places-{args.latitude:.4f}-{args.longitude:.4f}-{args.radius_km}.json'
    cache.parent.mkdir(parents=True, exist_ok=True)
    if args.input:
        data = args.input.read_bytes()
    elif args.refresh or not cache.exists():
        request = urllib.request.Request(
            'https://overpass.private.coffee/api/interpreter?' + urllib.parse.urlencode({'data': query}),
            headers={'User-Agent': 'RFTrafficMonitor/0.10 offline map builder'})
        data = urllib.request.urlopen(request, timeout=180).read()
        parsed = json.loads(data)
        if parsed.get('remark'):
            raise RuntimeError(parsed['remark'])
        cache.write_bytes(data)
    else:
        data = cache.read_bytes()
    data = json.loads(data)
    places, seen = [], set()
    order = {'city': 0, 'town': 1, 'village': 2, 'hamlet': 3, 'suburb': 4, 'neighbourhood': 5}
    for obj in data['elements']:
        tags = obj.get('tags', {})
        center = obj.get('center', obj)
        name = tags.get('name:en')
        if not name:
            local_name=tags.get('name','')
            name=local_name if local_name.isascii() else ''
        if any('\u0370' <= char <= '\u03ff' for char in name):
            continue
        if not name or 'lat' not in center:
            continue
        lat, lon = center['lat'], center['lon']
        key = (name, round(lat, 3), round(lon, 3))
        if key in seen:
            continue
        seen.add(key)
        places.append({'name': name, 'lat': lat, 'lon': lon,
                       'kind': tags['place'], 'osm': f"{obj['type']}/{obj['id']}"})
    places.sort(key=lambda place: (order[place['kind']], place['name']))
    output = ROOT / 'app/maps/places.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'source': 'OpenStreetMap contributors', 'license': 'ODbL 1.0',
                                  'timestamp': data.get('osm3s', {}).get('timestamp_osm_base'),
                                  'bounds': [round(v, 5) for v in bounds], 'places': places},
                                 ensure_ascii=False, separators=(',', ':')), 'utf-8')
    print(f'{len(places)} places; {output.stat().st_size} bytes')


if __name__ == '__main__':
    main()
