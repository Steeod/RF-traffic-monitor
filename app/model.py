"""Local track store. Position freshness never advances on metadata alone."""
import math
import threading
import time


def number(value, low, high):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and low <= result <= high else None
    except (TypeError, ValueError):
        return None


class Tracks:
    def __init__(self):
        self.lock = threading.RLock()
        self.items = {}

    def clear(self):
        with self.lock:
            self.items.clear()

    def update(self, kind, ident, fields, now=None):
        now = time.time() if now is None else now
        with self.lock:
            key = kind + ':' + str(ident)
            t = self.items.setdefault(key, {'id': key, 'ident': str(ident), 'kind': kind,
                                            'trail': [], 'position_time': None})
            t['heard_time'] = max(now,t.get('heard_time',now))
            lat, lon = number(fields.get('lat'), -90, 90), number(fields.get('lon'), -180, 180)
            older = lat is not None and lon is not None and now < (t['position_time'] or 0)
            for k, v in fields.items():
                if older and k in ('altitude','speed','course','source'):continue
                if k not in ('lat', 'lon') and v is not None and v != '':
                    t[k] = v
            if lat is not None and lon is not None and not older:
                t.update(lat=lat, lon=lon, position_time=now)
                if not t['trail'] or now - t['trail'][-1][2] >= 5:
                    t['trail'].append([lat, lon, now])
                    t['trail'] = t['trail'][-180:]
            if len(self.items) > 5000:
                oldest = min(self.items, key=lambda k: self.items[k]['heard_time'])
                del self.items[oldest]

    def aircraft(self, msg, now=None):
        ident = msg.get('Icao24')
        if not isinstance(ident, str) or len(ident) != 6:
            return
        try:
            int(ident, 16)
        except ValueError:
            return
        self.update('aircraft', ident, {
            'name': (msg.get('Callsign') or '').strip(),
            'lat': msg.get('Latitude'), 'lon': msg.get('Longitude'),
            'altitude': number(msg.get('Altitude'), -2000, 100000),
            'speed': number(msg.get('GroundSpeed'), 0, 2500),
            'course': number(msg.get('Track'), 0, 359.999), 'source': 'ADS-B / VRS'
        }, now)

    def vessel(self, msg, now=None):
        if msg.get('class') != 'AIS' or msg.get('scaled') is not True:
            return
        if msg.get('type') not in (1, 2, 3, 5, 18, 19, 24, 27):
            return
        ident = msg.get('mmsi')
        if not isinstance(ident, int) or not 10000000 <= ident <= 999999999:
            return
        self.update('vessel', ident, {
            'name': str(msg.get('shipname', '')).strip(' @'),
            'lat': msg.get('lat'), 'lon': msg.get('lon'),
            'speed': number(msg.get('speed'), 0, 62 if msg.get('type') == 27 else 102.2),
            'course': number(msg.get('course'), 0, 359.999),
            'destination': str(msg.get('destination', '')).strip(' @'), 'source': 'AIS'
        }, now)

    def snapshot(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            result = []
            for key, t in list(self.items.items()):
                ttl = {'aircraft':180,'vessel':1800,'sonde':1800,'drone':120}.get(t['kind'],180)
                if now - t['heard_time'] > 3600:
                    del self.items[key]
                    continue
                pt = t['position_time']
                if pt is None or now - pt > ttl:
                    continue
                age = max(0, now - pt)
                result.append({**t, 'trail': list(t['trail']), 'age': round(age, 1),
                               'stale': age > {'aircraft':15,'vessel':180,'sonde':120,'drone':10}.get(t['kind'],15)})
            return result


class Schedule:
    """Monotonic slots: ADS-B priority, one active decoder, no catch-up slots."""
    def __init__(self, adsb=60, ais=15, protocols=None, scan=None, allow_empty=False):
        if not 5 <= ais <= 30 or not 30 <= adsb <= 300 or adsb < 4 * ais:
            raise ValueError('ADS-B: 30–300 s, AIS: 5–30 s, ADS-B >= 4 × AIS')
        scan={'adsb':True,'ais':True} if scan is None else scan
        self.seconds = {'adsb': adsb, 'ais': ais}
        self.adsb=bool(scan.get('adsb'))
        self.aux = ['ais'] if scan.get('ais') else []
        for mode,p in (protocols or {}).items():
            self.seconds[mode]=p['seconds']
            if p['enabled']:
                if self.adsb and adsb < 4*p['seconds']:raise ValueError('ADS-B must be at least 4× each additional interval')
                self.aux.append(mode)
        if not self.adsb and not self.aux and not allow_empty:raise ValueError('Select at least one scanning mode')
        self.aux_index=0
        self.mode = 'stopped'
        self.deadline = None

    def start(self, mode, now):
        self.mode = mode
        self.deadline = now + self.seconds[mode]

    def due(self, now):
        return self.deadline is not None and now >= self.deadline

    def next(self):
        if self.adsb:
            if not self.aux:return 'adsb'
            if self.mode=='adsb':return self.aux[self.aux_index]
            self.aux_index=(self.aux_index+1)%len(self.aux);return 'adsb'
        if self.mode in self.aux:self.aux_index=(self.aux.index(self.mode)+1)%len(self.aux)
        return self.aux[self.aux_index]

    def cycle(self):
        """Return one complete receiver cycle in its actual execution order."""
        if self.adsb:
            return ['adsb'] if not self.aux else [mode for aux in self.aux for mode in ('adsb',aux)]
        return list(self.aux)
