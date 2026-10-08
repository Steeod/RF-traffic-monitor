import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'app'))
from server import Controller, validate_config
from model import Schedule, Tracks

class StartupScanTests(unittest.TestCase):
    def config(self):
        return validate_config(json.loads((ROOT/'app/config.example.json').read_text()))

    def controller(self):
        c = Controller.__new__(Controller)
        c.config = self.config(); c.policy = 'stopped'; c.mode = 'stop'
        c.radio = c.bridge = c.wifi = None
        c.wifi_available = True; c.wifi_reason = ''; c.tracks = Tracks()
        c.event = Mock(); c.stop_process = Mock(); c.spawn = Mock(return_value=Mock(poll=lambda:None))
        def switch(mode):
            c.mode = mode; c.radio = Mock(poll=lambda:None); c.schedule.start(mode, 100)
        c.switch = Mock(side_effect=switch)
        return c

    def test_toggle_preserves_single_receiver_and_stops_when_empty(self):
        c = self.controller()
        with tempfile.TemporaryDirectory() as folder, patch('server.ROOT', Path(folder)):
            c.toggle_scan('adsb', True)
            self.assertEqual(c.policy, 'auto'); self.assertIsNone(c.schedule.deadline)
            radio = c.radio
            c.toggle_scan('ais', True)
            self.assertIs(c.radio, radio); self.assertIsNotNone(c.schedule.deadline)
            c.toggle_scan('ais', False)
            self.assertIs(c.radio, radio); self.assertIsNone(c.schedule.deadline)
            self.assertFalse(c.schedule.due(1e20)); self.assertEqual(c.switch.call_count, 1)
            c.toggle_scan('adsb', False)
            self.assertEqual(c.policy, 'stopped'); self.assertIsNone(c.radio)
            self.assertEqual(c.schedule.cycle(), [])

    def test_remove_active_mode_switches_and_wifi_does_not_interrupt_sdr(self):
        c = self.controller()
        with tempfile.TemporaryDirectory() as folder, patch('server.ROOT', Path(folder)):
            c.toggle_scan('adsb', True); c.toggle_scan('ais', True)
            c.toggle_scan('adsb', False)
            self.assertEqual(c.mode, 'ais'); self.assertIsNone(c.schedule.deadline)
            radio = c.radio
            c.toggle_scan('wifi', True)
            self.assertIs(c.radio, radio); self.assertIsNone(c.schedule.deadline)
            c.toggle_scan('ais', False)
            self.assertEqual(c.mode, 'wifi'); self.assertIsNone(c.radio)
            c.toggle_scan('wifi', False)
            self.assertEqual(c.policy, 'stopped'); self.assertIsNone(c.wifi)

    def test_single_auxiliary_is_continuous(self):
        c = self.controller()
        with tempfile.TemporaryDirectory() as folder, patch('server.ROOT', Path(folder)):
            for mode in ('ais','acars','vdl2','hfdl','sonde'):
                c.toggle_scan(mode, True)
                self.assertEqual(c.schedule.cycle(), [mode]); self.assertIsNone(c.schedule.deadline)
                c.toggle_scan(mode, False)

    def test_setup_migration_and_explicit_zero_location(self):
        cfg = self.config(); self.assertFalse(cfg['setup_complete'])
        del cfg['setup_complete']; cfg['latitude'] = 45
        self.assertTrue(validate_config(cfg)['setup_complete'])
        cfg['latitude'] = 0; cfg['setup_complete'] = True
        self.assertTrue(validate_config(cfg)['setup_complete'])

    def test_demo_uses_visible_map_when_setup_is_missing(self):
        c = self.controller()
        with tempfile.TemporaryDirectory() as folder, patch('server.ROOT', Path(folder)):
            maps = Path(folder)/'maps'; maps.mkdir()
            (maps/'satellite.json').write_text(json.dumps({'center':[36,28]}))
            c.demo()
            tracks = c.tracks.snapshot()
            self.assertEqual(len(tracks), 8)
            self.assertTrue(all(35 < t['lat'] < 37 and 27 < t['lon'] < 29 for t in tracks))

if __name__ == '__main__': unittest.main()
