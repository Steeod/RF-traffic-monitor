import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from model import Tracks, Schedule
from server import Controller, identify_alfa_device, validate_config, wifi_interface_matches


class ModelTests(unittest.TestCase):
    def test_metadata_does_not_refresh_position(self):
        store = Tracks()
        store.vessel({'class':'AIS', 'scaled':True, 'type':1, 'mmsi':237000001,
                      'lat':36.4, 'lon':28.3}, 100)
        store.vessel({'class':'AIS', 'scaled':True, 'type':5, 'mmsi':237000001,
                      'shipname':'TEST VESSEL'}, 300)
        t = store.snapshot(301)[0]
        self.assertEqual(t['age'], 201)
        self.assertTrue(t['stale'])
        self.assertEqual(t['name'], 'TEST VESSEL')
        self.assertEqual(store.snapshot(1901), [])

    def test_aircraft_ages_while_tuned_elsewhere(self):
        store = Tracks()
        store.aircraft({'Icao24':'40621D','Latitude':36.2,'Longitude':28.2},100)
        store.aircraft({'Icao24':'40621D','Callsign':'NEW'},120)
        self.assertTrue(store.snapshot(121)[0]['stale'])
        self.assertEqual(store.snapshot(281), [])

    def test_ais_invalid_and_station_reports_not_plotted_as_ships(self):
        store = Tracks()
        for kind, lat, lon in [(4,36,28),(1,91,181),(1,float('nan'),28)]:
            store.vessel({'class':'AIS','scaled':True,'type':kind,'mmsi':237000001,
                          'lat':lat,'lon':lon}, 100)
        self.assertEqual(store.snapshot(101), [])

    def test_static_before_position_merges(self):
        store=Tracks()
        store.vessel({'class':'AIS','scaled':True,'type':24,'mmsi':237000001,'shipname':'TEST VESSEL'},100)
        self.assertEqual(store.snapshot(101),[])
        store.vessel({'class':'AIS','scaled':True,'type':18,'mmsi':237000001,'lat':36.3,'lon':28.3},110)
        self.assertEqual(store.snapshot(111)[0]['name'],'TEST VESSEL')

    def test_schedule_prioritizes_adsb(self):
        s=Schedule(60,15)
        s.start('adsb',100)
        self.assertFalse(s.due(159.9))
        self.assertTrue(s.due(160))
        self.assertEqual(s.next(),'ais')
        s.start(s.next(),162)
        self.assertEqual(s.deadline,177)
        self.assertEqual(s.next(),'adsb')
        for durations in [(30,15),(60,0),(60,31)]:
            with self.assertRaises(ValueError): Schedule(*durations)

    def test_full_cycle_reports_every_active_slot(self):
        from protocols import DEFAULTS
        protocols=json.loads(json.dumps(DEFAULTS))
        for settings in protocols.values():settings['enabled']=True
        schedule=Schedule(60,15,protocols)
        self.assertEqual(schedule.cycle(),['adsb','ais','adsb','acars','adsb','vdl2','adsb','hfdl','adsb','sonde'])

    def test_wifi_only_and_alfa_hardware_detection(self):
        self.assertEqual(identify_alfa_device('USB\\VID_0BDA&PID_8187\\123'),'awus036h')
        self.assertEqual(identify_alfa_device('USB\\VID_0BDA&PID_A811\\123'),'awus036acs')
        self.assertFalse(wifi_interface_matches('awus036h',['TP-Link Wireless USB Adapter']))
        self.assertTrue(wifi_interface_matches('awus036h',['Realtek RTL8187 Wireless 802.11b/g']))
        empty={name:{**settings,'enabled':False} for name,settings in __import__('protocols').DEFAULTS.items()}
        self.assertEqual(Schedule(60,15,empty,{'adsb':False,'ais':False},allow_empty=True).cycle(),[])

    def test_no_nan_configuration(self):
        c=json.loads((ROOT/'app/config.json').read_text())
        for key, value in [('latitude',float('nan')),('adsb_seconds',float('inf')),('device_index',True)]:
            with self.assertRaises(ValueError): validate_config({**c,key:value})


class BinaryTests(unittest.TestCase):
    @unittest.skipUnless((ROOT/'app/vendor/vrs/VrsBridge.exe').is_file(),
                         'Run setup.ps1 to build the Virtual Radar bridge.')
    def test_real_vrs_parser(self):
        line='MSG,3,1,1,40621D,1,2026/09/23,12:00:00.000,2026/09/23,12:00:00.000,,30000,,,36.3,28.2,,,0,0,0,0\n'
        run=subprocess.run([str(ROOT/'app/vendor/vrs/VrsBridge.exe'),'--stdin'],input=line,
                           text=True,capture_output=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        message=json.loads(run.stdout)
        tracks=Tracks();tracks.aircraft(message,100)
        t=tracks.snapshot(101)[0]
        self.assertEqual((t['lat'],t['lon'],t['altitude']),(36.3,28.2,30000))

    @unittest.skipUnless((ROOT/'app/vendor/ais/AIS-catcher.exe').is_file(),
                         'Run setup.ps1 to provision AIS-catcher.')
    def test_real_ais_decoder(self):
        nmea='!AIVDM,1,1,,B,3776k`5000a3SLPEKnDQQWpH0000,0*78\n'
        run=subprocess.run([str(ROOT/'app/vendor/ais/AIS-catcher.exe'),'-r','txt','.','-o','5'],
                           input=nmea,text=True,capture_output=True,timeout=10)
        messages=[json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
        self.assertTrue(messages,run.stderr)
        tracks=Tracks();tracks.vessel(messages[0],100)
        t=tracks.snapshot(101)[0]
        self.assertEqual(t['ident'],'477213600')
        self.assertAlmostEqual(t['lat'],37.460617,places=5)

    @unittest.skipUnless((ROOT/'app/maps/land.json').is_file(),
                         'Run setup.ps1 to generate the offline map.')
    def test_map_is_local_and_covers_region(self):
        data=json.loads((ROOT/'app/maps/land.json').read_text())
        west,south,east,north=data['bounds']
        self.assertTrue(-180<=west<east<=180 and -85<=south<north<=85)
        self.assertGreater(len(data['polygons']),0)
        for poly in data['polygons']:
            for ring in poly:
                self.assertEqual(ring[0],ring[-1])
                for lon,lat in ring:
                    self.assertTrue(west<=lon<=east and south<=lat<=north)


class ProcessTests(unittest.TestCase):
    def test_previous_radio_exits_before_next_spawns(self):
        class Process:
            def __init__(self): self.code=None
            def poll(self): return self.code
            def terminate(self): self.code=0; events.append('stop')
            def wait(self,timeout=None): return self.code
        c=Controller.__new__(Controller)
        import threading
        c.lock=threading.RLock();c.done=threading.Event()
        c.config=validate_config(json.loads((ROOT/'app/config.example.json').read_text()))
        c.rtl_selected_serial=''
        c.schedule=Schedule();c.mode='adsb';c.radio=Process();c.bridge=None
        events=[]
        def spawn(command, callback=None):
            events.append('spawn')
            self.assertEqual(events[0],'stop')
            self.assertEqual(command[1:3], ['-d', '00000001'])
            return Process()
        c.spawn=spawn;c.event=lambda message: None
        def discover(*args):
            self.assertEqual(events, ['stop'])
            events.append('discover')
            return {'index':0, 'serial':'00000001'}
        with patch.object(c.done,'wait',return_value=False), patch('server.resolve_rtl',side_effect=discover):
            c.switch('ais')
        self.assertEqual(events,['stop','discover','spawn'])
        self.assertEqual(c.mode,'ais')


if __name__=='__main__': unittest.main()
