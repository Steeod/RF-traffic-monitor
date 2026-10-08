"""Bounded, cached place search using Photon's public OpenStreetMap API."""
import collections
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

_lock = threading.Lock()
_cache = collections.OrderedDict()
_last_request = 0.0


def parse_places(data):
    if not isinstance(data, dict) or not isinstance(data.get('features'), list):
        raise ValueError('Invalid place search response')
    results = []
    seen = set()
    for feature in data['features'][:20]:
        try:
            props = feature['properties']
            lon, lat = feature['geometry']['coordinates']
            lat, lon = float(lat), float(lon)
            if not math.isfinite(lat) or not math.isfinite(lon) or not -85 <= lat <= 85 or not -180 <= lon <= 180:
                continue
            parts = []
            for key in ('name', 'city', 'state', 'country'):
                value = props.get(key)
                if isinstance(value, str) and value.strip() and value not in parts:
                    parts.append(value[:200])
            if not parts: continue
            label = ', '.join(parts)
            identity = (label, lat, lon)
            if identity in seen: continue
            seen.add(identity)
            results.append({'label': label, 'latitude': lat, 'longitude': lon})
        except (KeyError, TypeError, ValueError):
            continue
        if len(results) == 6: break
    return results


def search_places(query):
    global _last_request
    if not isinstance(query, str): raise ValueError('Enter a country, city or island.')
    query = ' '.join(query.split())
    if not 3 <= len(query) <= 160: raise ValueError('Enter between 3 and 160 characters.')
    key = query.casefold()
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
        time.sleep(max(0, 1.0 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        url = 'https://photon.komoot.io/api/?' + urllib.parse.urlencode({'q': query, 'limit': 6, 'lang': 'en'})
        request = urllib.request.Request(url, headers={'User-Agent': 'RFTrafficMonitor/0.10.3 (station setup)', 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read(262145)
            if len(raw) > 262144: raise ValueError('Response too large')
            places = parse_places(json.loads(raw))
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise LookupError('Place search is unavailable. Check your internet connection, retry, or enter coordinates manually.') from error
        _cache[key] = places
        while len(_cache) > 128: _cache.popitem(last=False)
        return places
