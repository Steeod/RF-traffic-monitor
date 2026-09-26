"""Crop Natural Earth land data around a configurable receiving station."""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def bounds_for(lat, lon, radius_km):
    margin = max(250.0, float(radius_km) * 1.25)
    dy = margin / 111.195
    dx = margin / (111.195 * max(0.15, math.cos(math.radians(lat))))
    return [max(-180.0, lon - dx), max(-85.0, lat - dy),
            min(180.0, lon + dx), min(85.0, lat + dy)]


def clip(ring, bounds):
    west, south, east, north = bounds
    pts = ring[:-1] if ring and ring[0] == ring[-1] else ring[:]
    for axis, bound, sign in ((0, west, 1), (0, east, -1),
                              (1, south, 1), (1, north, -1)):
        out = []
        for index, end in enumerate(pts):
            start = pts[index - 1]
            a = sign * (start[axis] - bound) >= 0
            b = sign * (end[axis] - bound) >= 0
            if a != b:
                delta = end[axis] - start[axis]
                if delta:
                    fraction = (bound - start[axis]) / delta
                    out.append([start[j] + fraction * (end[j] - start[j]) for j in (0, 1)])
            if b:
                out.append(end)
        pts = out
        if not pts:
            break
    return [[round(value, 5) for value in point] for point in pts + pts[:1]] if len(pts) >= 3 else []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('latitude', type=float)
    parser.add_argument('longitude', type=float)
    parser.add_argument('--radius-km', type=int, default=200)
    args = parser.parse_args()
    if not -85 <= args.latitude <= 85 or not -180 <= args.longitude <= 180:
        raise ValueError('Latitude must be -85..85 and longitude -180..180')
    bounds = bounds_for(args.latitude, args.longitude, args.radius_km)
    source = json.loads((ROOT / 'downloads/land.geojson').read_text('utf-8'))
    polygons = []
    for feature in source['features']:
        geometry = feature['geometry']
        source_polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
        for polygon in source_polygons:
            rings = [result for ring in polygon if (result := clip(ring, bounds))]
            if rings:
                polygons.append(rings)
    output = ROOT / 'app/maps/land.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'source': 'Natural Earth 1:10m, public domain',
                                  'bounds': [round(v, 5) for v in bounds],
                                  'center': [args.latitude, args.longitude],
                                  'polygons': polygons}, separators=(',', ':')), 'utf-8')
    print(output, output.stat().st_size)


if __name__ == '__main__':
    main()
