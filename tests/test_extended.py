import base64
import copy
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from model import Tracks,Schedule
from protocols import DEFAULTS,validate_protocols,ingest
from remote_id import RemoteID
from wifi_rid_worker import frames,vendor_messages,DLT_IEEE802_11_RADIO

class ExtendedTests(unittest.TestCase):
    def test_scan_controls_are_directly_below_mode_buttons(self):
        html=(ROOT/'app/web/index.html').read_text('utf-8')
        controls=html.index('id="auto"')
        scans=html.index('Scanning options with ✓')
        error=html.index('id="error"')
        self.assertLess(controls,scans);self.assertLess(scans,error)
        self.assertNotIn('manual-mode',html);self.assertNotIn('listen-extra',html)
        self.assertNotIn('id="adsb"',html);self.assertNotIn('id="ais"',html)
        self.assertNotIn('Continuous reception',html)
        self.assertIn('id="scan-wifi"',html)
        self.assertIn('id="cycle-bar"',html)
        self.assertIn('id="wifi-quick-install"',html)
        self.assertGreaterEqual(html.count('Made by Steeod'),2)
        receiver=html.index('Receiver, station, map, and drivers')
        decoded=html.index('<details><summary>Decoded messages')
        self.assertGreater(html.index('id="background-file"'),receiver)
        self.assertLess(html.index('id="background-file"'),decoded)
        self.assertNotIn('<summary>Drone · Wi-Fi Remote ID',html)
        self.assertGreater(html.index('id="protocol-fields"'),decoded)

    @unittest.skipUnless((ROOT/'app/vendor/drivers/alfa/awus036h/Netrtuw.inf').is_file(),
                         'Run setup.ps1 to provision the driver packages.')
    def test_alfa_driver_profiles_are_packaged(self):
        drivers=ROOT/'app/vendor/drivers/alfa'
        h=(drivers/'awus036h/Netrtuw.inf').read_text(errors='ignore')
        acs=(drivers/'awus036acs/netrtwlanu.inf').read_text('utf-16')
        self.assertIn('USB\\VID_0BDA&PID_8187',h)
        self.assertIn('USB\\VID_0BDA&PID_0811',acs)
        self.assertTrue((drivers/'awus036h/netrtuw.cat').is_file())
        self.assertTrue((drivers/'awus036acs/netrtwlanu.cat').is_file())
        self.assertTrue((ROOT/'app/wsl/setup-rtl8811au.sh').is_file())
        self.assertIn('rtw88-master.zip', (ROOT/'app/wsl/setup-rtl8811au.sh').read_text('utf-8'))

    def test_all_modes_alternate_with_adsb(self):
        modes=copy.deepcopy(DEFAULTS)
        for p in modes.values():p['enabled']=True
        clock=Schedule(60,15,modes);observed=[]
        clock.start('adsb',0)
        for _ in range(10):
            mode=clock.next();observed.append(mode);clock.start(mode,0)
        self.assertEqual(observed,['ais','adsb','acars','adsb','vdl2','adsb','hfdl','adsb','sonde','adsb'])

    def test_frequency_window_and_priority_validation(self):
        cfg=copy.deepcopy(DEFAULTS);cfg['acars']['frequencies']=[118000000,137000000]
        with self.assertRaises(ValueError):validate_protocols(cfg)
        cfg=copy.deepcopy(DEFAULTS);cfg['acars']['seconds']=20
        with self.assertRaises(ValueError):Schedule(60,15,cfg)

    def test_scan_checkboxes_control_schedule(self):
        cfg=copy.deepcopy(DEFAULTS)
        for p in cfg.values():p['enabled']=False
        cfg['sonde']['enabled']=True
        clock=Schedule(60,15,cfg,{'adsb':False,'ais':True})
        clock.start('ais',0)
        self.assertEqual(clock.next(),'sonde');clock.start('sonde',1)
        self.assertEqual(clock.next(),'ais')
        with self.assertRaises(ValueError):Schedule(60,15,{k:{**v,'enabled':False} for k,v in cfg.items()},{'adsb':False,'ais':False})

    def test_telemetry_requires_position_and_valid_crc(self):
        tracks=Tracks()
        message={'decode':{'crc_ok':True},'body':{'type':'acars','tail':'TEST','text':'DEST 36.2 28.1'}}
        ingest(tracks,'acars',message,100);self.assertEqual(tracks.snapshot(100),[])
        # Synthetic decoded RS41 message: exercises ingestion without publishing
        # the local off-air reference fixture.
        sample={'decode':{'crc_ok':True},'body':{'type':'sonde','kind':'rs41','details':{
            'serial':'TEST-RS41','crc':{'gps_pos':True},
            'gps_pos':{'lat':36.2,'lon':28.1,'alt_m':1000,'speed_ms':12,
                       'course_deg':90,'num_sv':8}}}}
        ingest(tracks,'sonde',sample,100)
        self.assertEqual(tracks.snapshot(100)[0]['ident'],'TEST-RS41')
        self.assertAlmostEqual(tracks.snapshot(100)[0]['lat'],36.2,places=5)
        sample['body']['details']['gps_pos']['lat']=35.9
        sample['decode']['crc_ok']=False
        ingest(tracks,'sonde',sample,101)
        self.assertAlmostEqual(tracks.snapshot(101)[0]['lat'],36.2,places=5)

    def test_adsc_ignores_predictions_and_old_reports(self):
        tracks=Tracks();app={'app':'adsc','crc_ok':True,'err':False,'tags':[
            {'tag':'fixed_projection','lat':30,'lon':20},
            {'tag':'report','lat':36.2,'lon':28.1,'accuracy':7,'timestamp_s':95,'alt_ft':12000}]}
        message={'decode':{'crc_ok':True},'body':{'type':'acars','tail':'TEST','app':app}}
        ingest(tracks,'vdl2',message,100)
        self.assertEqual(tracks.snapshot(100)[0]['age'],5)
        self.assertEqual(tracks.snapshot(100)[0]['lat'],36.2)
        app['tags'][1]['timestamp_s']=1
        ingest(tracks,'vdl2',message,500)
        self.assertEqual(tracks.snapshot(500),[])

    @unittest.skipUnless((ROOT/'app/vendor/native/rid_decode.dll').is_file(),
                         'Run setup.ps1 to build the Remote ID decoder.')
    def test_remote_id_wire_packet_and_duplicates(self):
        # ASTM location layout; integer WGS84 coordinates and half-metre heights.
        packet=struct.pack('<BBBBbiiHHHBBHBB',0x12,0x20,90,20,0,
                           362000000,281000000,2200,2240,2160,0,0,1000,0,0)
        basic=bytes([0x02,0x12])+b'TEST-DRONE'.ljust(20,b'\0')+bytes(3)
        message={'address':'AABBCCDDEEFF','rssi':-62,
            'data':base64.b64encode(b'\xfa\xff\x0d\x01'+bytes([0xf2,25,2])+basic+packet).decode()}
        tracks=Tracks();decoder=RemoteID(tracks)
        self.assertEqual(decoder.ingest(message,100),1)
        target=tracks.snapshot(100)[0]
        self.assertEqual(target['name'],'TEST-DRONE')
        self.assertAlmostEqual(target['lat'],36.2)
        self.assertAlmostEqual(target['lon'],28.1)
        self.assertAlmostEqual(target['altitude'],120*3.28084)
        self.assertEqual(decoder.ingest(message,105),0)
        self.assertEqual(tracks.snapshot(105)[0]['age'],5)
        self.assertEqual(tracks.snapshot(221),[])
        message['data']=base64.b64encode(b'\xfa\xff\x0d\x01'+bytes([0xf2,25,9])+packet).decode()
        self.assertEqual(decoder.ingest(message,222),0)

    @unittest.skipUnless((ROOT/'app/vendor/native/rid_decode.dll').is_file(),
                         'Run setup.ps1 to build the Remote ID decoder.')
    def test_wifi_beacon_remote_id_extraction(self):
        packet=struct.pack('<BBBBbiiHHHBBHBB',0x12,0x20,90,20,0,
                           362000000,281000000,2200,2240,2160,0,0,1000,0,0)
        basic=bytes([0x02,0x12])+b'WIFI-DRONE'.ljust(20,b'\0')+bytes(3)
        payload=bytes([0xf2,25,2])+basic+packet
        radiotap=b'\x00\x00\x08\x00\x00\x00\x00\x00'
        header=b'\x80\x00'+bytes(8)+bytes.fromhex('AABBCCDDEEFF')+bytes(8)
        beacon_fixed=bytes(12)
        vendor=bytes([221,len(payload)+4])+b'\xfa\x0b\xbc\x0d'+payload
        found=list(frames(radiotap+header+beacon_fixed+vendor,DLT_IEEE802_11_RADIO))
        self.assertEqual(found[0]['address'],'AABBCCDDEEFF')
        tracks=Tracks();decoder=RemoteID(tracks)
        self.assertEqual(decoder.ingest_wifi(found[0],100),1)
        target=tracks.snapshot(100)[0]
        self.assertEqual(target['name'],'WIFI-DRONE')
        self.assertEqual(target['source'],'Remote ID / Wi-Fi')

    def test_windows_wlan_information_element_extraction(self):
        payload=bytes(range(25))
        ies=b'\x00\x03abc'+bytes([221,len(payload)+4])+b'\xfa\x0b\xbc\x0d'+payload
        found=list(vendor_messages(ies,'001122334455',-47))
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['address'],'001122334455')
        self.assertEqual(found[0]['rssi'],-47)
        self.assertEqual(base64.b64decode(found[0]['data']),payload)

if __name__=='__main__':unittest.main()
