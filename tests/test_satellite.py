"""Verify actual packaged imagery coverage and the loopback HTTP boundary."""
import http.client
import json
import math
from pathlib import Path
import sqlite3
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from server import Handler

@unittest.skipUnless((ROOT/'app/maps/satellite.json').exists(), 'Satellite build not complete')
class SatelliteTests(unittest.TestCase):
    def test_complete_pyramid_and_configured_buffer(self):
        with sqlite3.connect(ROOT/'app/maps/satellite.sqlite') as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            manifest=json.loads((ROOT/'app/maps/satellite.json').read_text())
            levels=manifest['levels']
            for z,(xmin,ymin,xmax,ymax) in levels.items():
                count=db.execute('SELECT count(*) FROM tiles WHERE z=?',(int(z),)).fetchone()[0]
                self.assertEqual(count,(xmax-xmin+1)*(ymax-ymin+1))
            lat,lon=manifest.get('center',(36.2,27.95));angle=manifest.get('radius_km',200)/6371
            phi,lam=map(math.radians,(lat,lon))
            for bearing in range(0,360,5):
                b=math.radians(bearing)
                p=math.asin(math.sin(phi)*math.cos(angle)+math.cos(phi)*math.sin(angle)*math.cos(b))
                l=lam+math.atan2(math.sin(b)*math.sin(angle)*math.cos(phi),math.cos(angle)-math.sin(phi)*math.sin(p))
                x=int((math.degrees(l)+180)/360*4096)
                y=int((1-math.asinh(math.tan(p))/math.pi)/2*4096)
                self.assertIsNotNone(db.execute('SELECT 1 FROM tiles WHERE z=12 AND x=? AND y=?',(x,y)).fetchone())

    def test_local_http_tiles_and_security(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.controller=type('Controller',(),{'token':'test-only'})()
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            conn.request('GET','/satellite.json');response=conn.getresponse()
            self.assertEqual(response.status,200)
            manifest=json.loads(response.read());x,y,_,_=manifest['levels']['14']
            conn.request('GET',f'/tiles/14/{x}/{y}.jpg');response=conn.getresponse()
            self.assertEqual(response.status,200);self.assertTrue(response.read().startswith(b'\xff\xd8'))
            conn.request('GET','/tiles/14/0/0.jpg');response=conn.getresponse()
            self.assertEqual(response.status,404);response.read()
            conn.request('GET','/satellite.json',headers={'Host':'external.example'})
            response=conn.getresponse();self.assertEqual(response.status,403);response.read()
            conn.request('POST','/api/command',body='{"action":"auto"}')
            response=conn.getresponse();self.assertEqual(response.status,403);response.read()
            conn.close()
        finally:
            server.shutdown();server.server_close();worker.join()

if __name__=='__main__':unittest.main()
