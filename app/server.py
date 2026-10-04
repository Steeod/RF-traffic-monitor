"""RF Traffic Monitor by Steeod: Windows portable, loopback-only UI."""
import argparse
import collections
from contextlib import closing
import ctypes
from ctypes import wintypes
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
from pathlib import Path
import queue
import re
import sqlite3
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import webbrowser

from model import Tracks, Schedule
from protocols import validate_protocols, ingest
from remote_id import RemoteID
from rtl_devices import resolve as resolve_rtl

ROOT = Path(__file__).resolve().parent
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
__author__ = 'Steeod'

ALFA_DEVICE_IDS = {
    'awus036h': ('VID_0BDA&PID_8187',),
    'awus036acs': ('VID_0BDA&PID_0811','VID_0BDA&PID_A811','VID_7392&PID_A811'),
}


def identify_alfa_device(device_text):
    text=device_text.upper()
    for model,identifiers in ALFA_DEVICE_IDS.items():
        if any(identifier in text for identifier in identifiers):return model
    return ''


def wifi_interface_matches(model, interfaces):
    if model in ('auto','other'):return bool(interfaces)
    needles={'awus036h':('8187','awus036h'),'awus036acs':('8811','awus036acs')}.get(model,())
    return any(any(needle in name.lower() for needle in needles) for name in interfaces)


class Job:
    """Windows kills all owned children if the controller exits unexpectedly."""
    def __init__(self):
        self.handle = None
        if os.name != 'nt':
            return
        class BASIC(ctypes.Structure):
            _fields_ = [('user', ctypes.c_int64), ('job', ctypes.c_int64),
                        ('flags', wintypes.DWORD), ('min', ctypes.c_size_t),
                        ('max', ctypes.c_size_t), ('count', wintypes.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                        ('scheduling', wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ('r', 'w', 'o', 'rb', 'wb', 'ob')]
        class LIMIT(ctypes.Structure):
            _fields_ = [('basic', BASIC), ('io', IO), ('process_mem', ctypes.c_size_t),
                        ('job_mem', ctypes.c_size_t), ('peak_process', ctypes.c_size_t),
                        ('peak_job', ctypes.c_size_t)]
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        limit = LIMIT()
        limit.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limit), ctypes.sizeof(limit)):
            raise ctypes.WinError(ctypes.get_last_error())

    def add(self, process):
        if self.handle and not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            process.kill()
            process.wait()
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def validate_config(config):
    config['station_name']=config.get('station_name','Receiving station')
    config['wifi_model']=config.get('wifi_model','awus036h')
    config['wifi_backend']=config.get('wifi_backend','windows')
    config['wifi_adapter']=config.get('wifi_adapter','')
    config['wsl_busid']=config.get('wsl_busid','')
    config['wifi_enabled']=config.get('wifi_enabled',False)
    config['map_latitude']=config.get('map_latitude',config.get('latitude',0.0))
    config['map_longitude']=config.get('map_longitude',config.get('longitude',0.0))
    config['receiver_type']=config.get('receiver_type','rtl')
    config['rtl_serial']=config.get('rtl_serial','')
    if not isinstance(config['rtl_serial'],str) or len(config['rtl_serial'])>256 or (config['rtl_serial'] and not config['rtl_serial'].isprintable()):
        raise ValueError('Invalid RTL-SDR serial number.')
    config['hackrf_serial']=config.get('hackrf_serial','')
    config['hackrf_lna']=config.get('hackrf_lna',16)
    config['hackrf_vga']=config.get('hackrf_vga',20)
    config['hackrf_amp']=config.get('hackrf_amp',False)
    config['scan']=config.get('scan',{'adsb':True,'ais':True})
    if not isinstance(config['station_name'],str) or not 1<=len(config['station_name'].strip())<=50 or any(ord(c)<32 for c in config['station_name']):
        raise ValueError('The station name must contain 1–50 characters.')
    config['station_name']=config['station_name'].strip()
    if config['wifi_model'] not in ('auto','awus036h','awus036acs','other'):raise ValueError('Unknown Wi-Fi adapter profile.')
    if config['wifi_backend'] not in ('windows','npcap','wsl'):raise ValueError('Unknown Wi-Fi backend.')
    if not isinstance(config['wsl_busid'],str) or (config['wsl_busid'] and not re.fullmatch(r'\d+-\d+',config['wsl_busid'])):raise ValueError('Invalid WSL USB BUSID.')
    if type(config['wifi_enabled']) is not bool:raise ValueError('Invalid Wi-Fi Remote ID selection.')
    if not isinstance(config['wifi_adapter'],str) or len(config['wifi_adapter'])>512 or any(ord(c)<32 for c in config['wifi_adapter']):
        raise ValueError('Invalid Wi-Fi adapter identifier.')
    if config['receiver_type'] not in ('rtl','hackrf','wifi'):raise ValueError('Unknown receiver type.')
    if not isinstance(config['hackrf_serial'],str) or len(config['hackrf_serial'])>64 or not re.fullmatch(r'[0-9A-Fa-f]*',config['hackrf_serial']):
        raise ValueError('The HackRF serial number must be hexadecimal.')
    if type(config['hackrf_lna']) is not int or config['hackrf_lna'] not in range(0,41,8):raise ValueError('HackRF LNA must be 0–40 dB in 8 dB steps.')
    if type(config['hackrf_vga']) is not int or config['hackrf_vga'] not in range(0,63,2):raise ValueError('HackRF VGA must be 0–62 dB in 2 dB steps.')
    if type(config['hackrf_amp']) is not bool:raise ValueError('Invalid HackRF amplifier setting.')
    if not isinstance(config['scan'],dict) or set(config['scan']) != {'adsb','ais'} or any(type(v) is not bool for v in config['scan'].values()):
        raise ValueError('Invalid scanning options.')
    if any(type(config[k]) is not int for k in ('adsb_seconds', 'ais_seconds')):
        raise ValueError('Reception times must be whole seconds.')
    config['protocols']=validate_protocols(config.get('protocols'))
    Schedule(config['adsb_seconds'], config['ais_seconds'],config['protocols'],config['scan'],config['receiver_type']=='wifi')
    if not -85 <= float(config['latitude']) <= 85 or not -180 <= float(config['longitude']) <= 180:
        raise ValueError('Invalid station location.')
    if not -85 <= float(config['map_latitude']) <= 85 or not -180 <= float(config['map_longitude']) <= 180:
        raise ValueError('Invalid map center.')
    if type(config['device_index']) is not int or not 0 <= config['device_index'] <= 16:
        raise ValueError('Invalid device number.')
    if type(config['ppm']) is not int or not -150 <= config['ppm'] <= 150:
        raise ValueError('PPM must be an integer from -150 to 150.')
    return config


class Controller:
    def __init__(self):
        self.config = validate_config(json.loads((ROOT / 'config.json').read_text('utf-8-sig')))
        self.tracks = Tracks()
        self.schedule = Schedule(self.config['adsb_seconds'], self.config['ais_seconds'],self.config['protocols'],self.config['scan'],self.config['receiver_type']=='wifi')
        self.commands = queue.Queue()
        self.done = threading.Event()
        self.lock = threading.RLock()
        self.job = Job()
        self.radio = None
        self.bridge = None
        self.wifi = None
        self.remote = RemoteID(self.tracks)
        self.remote_status = 'Wi-Fi Remote ID inactive'
        self.wifi_adapters = []
        self.wifi_available=False
        self.wifi_hardware=''
        self.wifi_interfaces=[]
        self.wifi_reason='No compatible Wi-Fi receiver was found.'
        self.wifi_seen = {}
        self.device_status = 'The device has not been checked.'
        self.rtl_selected_serial = ''
        self.zadig_opened_automatically = False
        self.map_download=None
        self.map_download_status=''
        self.messages = collections.deque(maxlen=100)
        self.policy = 'stopped'
        self.mode = 'stopped'
        self.error = ''
        self.token = secrets.token_urlsafe(32)
        self.events = collections.deque(maxlen=30)
        self.last_message = {k:None for k in ('adsb','ais','acars','vdl2','hfdl','sonde','remoteid')}
        self.counts = dict.fromkeys(self.last_message,0)
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.refresh_wifi()
        self.thread.start()

    def event(self, message):
        logging.info(message)
        with self.lock:
            self.events.appendleft({'time': time.time(), 'text': message})

    def dependencies(self):
        checks=[]
        def add(name,ok,help):checks.append({'name':name,'ok':bool(ok),'help':help})
        add('RTL-SDR / AIS-catcher',(ROOT/'vendor/ais/AIS-catcher.exe').exists(),'Included in the portable package. If missing, extract the entire ZIP again.')
        add('ADS-B dump1090',(ROOT/'vendor/adsb/dump1090.exe').exists(),'Included in the portable package. If missing, extract the entire ZIP again.')
        add('HackRF runtime',(ROOT/'vendor/ais/hackrf.dll').exists(),'Requires the bundled HackRF runtime and WinUSB through Zadig.')
        add('Npcap',(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/Npcap/wpcap.dll').exists(),'Install Npcap with raw 802.11 support only for the Npcap backend.')
        add('Microsoft WSL',shutil.which('wsl.exe'),'Enable WSL2 and install Ubuntu 22.04 from Windows.')
        add('usbipd-win',shutil.which('usbipd.exe'),'Select “usbipd installer”; the MSI is included in the portable package.')
        bundle=ROOT/'vendor/wsl-bundle'
        add('WSL offline source bundle',all((bundle/n).exists() for n in ('usbipd-win_5.3.0_x64.msi','rtw88-master.zip','rtl8812au-v5.6.4.2.zip','WSL2-Linux-Kernel-6.6.87.2.zip','manifest.json')),'Files are missing from vendor/wsl-bundle; extract the entire ZIP again.')
        return checks

    def spawn(self, command, callback=None):
        proc = subprocess.Popen(command, cwd=str(Path(command[0]).parent),
                                stdin=subprocess.PIPE if Path(command[0]).name.lower()=='python.exe' and any('hackrf_worker.py' in str(part) for part in command) else None,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding='utf-8', errors='replace',
                                creationflags=NO_WINDOW)
        self.job.add(proc)
        proc.diagnostics=[]
        def reader(stream, handler):
            for line in iter(stream.readline, ''):
                line = line.strip()
                if handler:
                    try:
                        handler(json.loads(line))
                    except (ValueError, TypeError, KeyError):
                        logging.debug('Non-JSON decoder output: %s', line[:500])
                elif line:
                    proc.diagnostics.append(line[:500])
                    if len(proc.diagnostics)>30:del proc.diagnostics[:-30]
                    logging.info('%s: %s', Path(command[0]).name, line[:500])
            stream.close()
        for stream, handler in ((proc.stdout, callback), (proc.stderr, None)):
            threading.Thread(target=reader, args=(stream, handler), daemon=True).start()
        return proc

    @staticmethod
    def stop_process(proc):
        if proc and proc.poll() is None:
            if getattr(proc,'stdin',None):
                try:
                    proc.stdin.close()
                    proc.wait(timeout=3)
                    return
                except (BrokenPipeError, OSError, subprocess.TimeoutExpired):pass
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)

    @staticmethod
    def decoder_error(proc, receiver):
        detail='\n'.join(getattr(proc,'diagnostics',())).lower()
        if 'usb_open error -5' in detail or 'usb_open error -12' in detail:
            return 'RTL-SDR was found but Windows could not open it. Install WinUSB with Zadig and close any other SDR application.'
        if 'no supported' in detail:
            return 'No usable RTL-SDR was found. Connect it, install WinUSB with Zadig, and run Check receiver.'
        if 'device does not exist' in detail or 'cannot find device with sn' in detail:
            return 'The selected RTL-SDR is missing from this decoder\'s device list. Stop and run Check receiver.'
        if 'hackrf open: error -5' in detail:
            return 'HackRF was found but is busy or still locked. Close other SDR applications, reconnect it, and run Check receiver.'
        return f'{receiver} stopped unexpectedly. Check the USB connection, driver, antenna, and data/radar.log.'

    def launch_zadig(self, automatic=False):
        installer=ROOT/'vendor/drivers/zadig-2.9.exe'
        if automatic and self.zadig_opened_automatically:return False
        if not installer.exists():
            if automatic:return False
            raise ValueError('Zadig is missing from the package.')
        if os.name=='nt':
            result=ctypes.windll.shell32.ShellExecuteW(None,'runas',str(installer),None,str(ROOT),1)
            if result<=32:raise OSError(f'Windows could not start Zadig (ShellExecute error {result}).')
        else:
            subprocess.Popen([str(installer)],cwd=str(ROOT))
        if automatic:self.zadig_opened_automatically=True
        self.device_status=('Zadig opened automatically because RTL-SDR was detected without a working WinUSB driver. '
                            'Select Options → List All Devices, choose only RTL-SDR, and select WinUSB.')
        return True

    def received(self, mode, message):
        with self.lock:
            if self.mode != mode or self.policy in ('demo', 'stopped'):
                return
            if message.get('status'):return
            self.last_message[mode] = time.time()
            self.counts[mode] += 1
            if mode == 'adsb':
                self.tracks.aircraft(message)
            elif mode=='ais':
                self.tracks.vessel(message)
            else:
                entry=ingest(self.tracks,mode,message)
                if entry:self.messages.appendleft({**entry,'time':time.time()})

    def received_remote(self,message):
        with self.lock:
            if message.get('status'):
                self.remote_status='Wi-Fi Remote ID: '+message.get('error',message['status'])
            else:
                count=self.remote.ingest_wifi(message)
                if self.remote.validated:
                    now=time.time();address=message.get('address','unknown')
                    self.counts['remoteid']+=1;self.last_message['remoteid']=now
                    self.remote_status='Wi-Fi Remote ID detected · '+address
                    if now-self.wifi_seen.get(address,0)>30:self.event('Wi-Fi Remote ID detected · '+address)
                    self.wifi_seen[address]=now

    def wifi_tool(self,*args):
        return subprocess.run([sys.executable,str(ROOT/'wifi_rid_worker.py'),*args],capture_output=True,text=True,
                              timeout=12,creationflags=NO_WINDOW)

    def refresh_wifi(self):
        self.wifi_available=False
        self.wifi_hardware=''
        if os.name=='nt':
            try:
                devices=subprocess.run(['pnputil.exe','/enum-devices','/connected','/ids'],capture_output=True,
                                       text=True,errors='replace',timeout=15,creationflags=NO_WINDOW)
                self.wifi_hardware=identify_alfa_device(devices.stdout)
            except Exception:pass
        try:
            if self.config['wifi_backend']=='wsl':
                result=subprocess.run([sys.executable,str(ROOT/'wsl_wifi.py'),'--status'],capture_output=True,text=True,timeout=25,creationflags=NO_WINDOW)
                data=json.loads(result.stdout.strip().splitlines()[-1]);self.wifi_available=bool(data.get('ready'))
                missing=[]
                if not data.get('usbipd'):missing.append('usbipd-win')
                if not data.get('driver'):missing.append('RTL8811AU driver')
                if not data.get('interface'):missing.append('attached Alfa adapter')
                self.wifi_reason='WSL2 monitor mode is ready.' if self.wifi_available else 'WSL2 missing: '+', '.join(missing)
            else:
                result=self.wifi_tool('--check-wlan');data=json.loads(result.stdout.strip().splitlines()[-1])
                self.wifi_interfaces=data.get('interfaces',[]) if result.returncode==0 else []
                selected=self.config['wifi_model']
                if selected=='auto' and self.wifi_hardware:selected=self.wifi_hardware
                self.wifi_available=wifi_interface_matches(selected,self.wifi_interfaces)
                if self.wifi_available:
                    self.wifi_reason='Selected Wi-Fi receiver ready: '+', '.join(self.wifi_interfaces)
                elif self.wifi_hardware:
                    label='Alfa AWUS036H / RTL8187' if self.wifi_hardware=='awus036h' else 'Alfa AWUS036ACS / RTL8811AU'
                    others=(' Other WLAN interfaces: '+', '.join(self.wifi_interfaces)+'.') if self.wifi_interfaces else ''
                    self.wifi_reason=label+' is connected, but Windows reports Problem Code 28: no usable driver.'+others+' Install the bundled signed Alfa driver below.'
                elif self.wifi_interfaces:
                    self.wifi_reason='The selected Wi-Fi model is not available. Detected: '+', '.join(self.wifi_interfaces)
                else:self.wifi_reason='No compatible Windows Wi-Fi adapter was found.'
        except Exception:self.wifi_reason='The Wi-Fi backend check did not complete.'

    def received_map(self,message):
        if message.get('status')=='progress':self.map_download_status=message.get('text','Downloading map…')
        elif message.get('status')=='done':
            self.map_download_status='The new offline region is ready. Refresh the page.'
            self.event('The offline map was updated.')
        elif message.get('status')=='error':
            self.map_download_status='Map download error: '+message.get('error','unknown error')

    def select_rtl(self, mode):
        backend = mode if mode in ('adsb', 'ais') else 'native'
        device = resolve_rtl(ROOT, backend, self.config['device_index'],
                             self.config['rtl_serial'] or self.rtl_selected_serial)
        self.rtl_selected_serial = device['serial']
        self.device_status = f"RTL-SDR serial {device['serial']} · {backend} index {device['index']} · opened successfully"
        logging.info(self.device_status)
        return device

    def switch(self, mode):
        # Stop and wait for exit BEFORE any process may reopen the one physical SDR.
        with self.lock:
            self.mode = 'switching'
        self.stop_process(self.radio)
        self.radio = None
        if self.done.wait(1):
            return
        cfg = self.config
        if cfg['receiver_type']=='rtl':
            rtl_device = self.select_rtl(mode)
        if cfg['receiver_type']=='hackrf':
            frequencies=cfg['protocols'].get(mode,{}).get('frequencies',[1090000000 if mode=='adsb' else 162000000])
            command=[sys.executable,str(ROOT/'hackrf_worker.py'),mode,cfg['hackrf_serial'],
                     str(cfg['hackrf_lna']),str(cfg['hackrf_vga']),'1' if cfg['hackrf_amp'] else '0',str(cfg['ppm']),
                     ','.join(str(f) for f in frequencies),str(cfg['latitude']),str(cfg['longitude'])]
            callback=lambda msg:self.received(mode,msg)
        elif mode == 'adsb':
            with socket.socket() as check:
                if os.name == 'nt':
                    check.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                check.bind(('127.0.0.1', 30003))
            command = [str(ROOT / 'vendor/adsb/dump1090.exe'), '--net', '--net-bind-address',
                       '127.0.0.1', '--net-http-port', '0', '--net-ri-port', '0',
                       '--net-ro-port', '0', '--net-bi-port', '0', '--net-bo-port', '0',
                       '--net-sbs-port', '30003', '--quiet', '--device-index', str(rtl_device['index']),
                       '--ppm', str(cfg['ppm']), '--lat', str(cfg['latitude']), '--lon', str(cfg['longitude'])]
            callback = None
        elif mode=='ais':
            command = [str(ROOT / 'vendor/ais/AIS-catcher.exe'), '-d', rtl_device['serial'],
                       '-o', '5', '-M', 'T', '-p', str(cfg['ppm']), '-gr', 'TUNER', 'auto',
                       'RTLAGC', 'on', 'BIASTEE', 'off']
            callback = lambda msg: self.received('ais', msg)
        else:
            command=[sys.executable,str(ROOT/'rtl_worker.py'),mode,str(rtl_device['index']),str(cfg['ppm']),
                     ','.join(str(f) for f in cfg['protocols'][mode]['frequencies'])]
            callback=lambda msg:self.received(mode,msg)
        with self.lock:
            self.mode = mode
        self.radio = self.spawn(command, callback)
        if self.done.wait(1):
            return
        if self.radio.poll() is not None:
            raise RuntimeError(self.decoder_error(self.radio,'HackRF' if cfg['receiver_type']=='hackrf' else 'RTL-SDR'))
        if mode == 'adsb' and (self.bridge is None or self.bridge.poll() is not None):
            self.bridge = self.spawn([str(ROOT / 'vendor/vrs/VrsBridge.exe')],
                                     lambda msg: self.received('adsb', msg))
        with self.lock:
            self.schedule.start(mode, time.monotonic())
        self.event('Receiving ' + mode.upper())

    def command(self, action, value=None):
        self.commands.put((action, value))

    def run(self):
        try:
            while not self.done.is_set():
                try:
                    action, value = self.commands.get(timeout=0.25)
                except queue.Empty:
                    action = None
                try:
                    if action == 'config':
                        if self.policy != 'stopped':
                            raise ValueError('Select Stop before changing settings.')
                        self.config = validate_config(value)
                        self.rtl_selected_serial = ''
                        path = ROOT / 'config.json'
                        temp = path.with_suffix('.tmp')
                        temp.write_text(json.dumps(value, indent=2), 'utf-8')
                        temp.replace(path)
                        self.schedule = Schedule(value['adsb_seconds'], value['ais_seconds'],value['protocols'],value['scan'],value['receiver_type']=='wifi')
                        self.refresh_wifi()
                        self.event('Settings saved.')
                    elif action=='device_check':
                        if self.policy!='stopped':raise ValueError('Select Stop before checking the device.')
                        if self.config['receiver_type']=='wifi':
                            self.refresh_wifi()
                            self.device_status=self.wifi_reason
                        elif self.config['receiver_type']=='hackrf':
                            result=subprocess.run([sys.executable,str(ROOT/'hackrf_worker.py'),'--check'],capture_output=True,text=True,timeout=10,creationflags=NO_WINDOW)
                            self.device_status='HackRF: '+(('detected and opened successfully') if result.returncode==0 else 'could not be opened · check the connection and WinUSB')
                        else:
                            self.rtl_selected_serial = ''
                            modes = [m for m, enabled in self.config['scan'].items() if enabled]
                            if any(p['enabled'] for p in self.config['protocols'].values()):modes.append('native')
                            statuses = []
                            try:
                                for mode in modes or ['adsb']:
                                    self.select_rtl(mode)
                                    statuses.append(self.device_status)
                                self.device_status = '; '.join(statuses)
                            except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
                                self.device_status = '; '.join(statuses + [str(error)])
                                raise
                    elif action=='driver_setup':
                        self.launch_zadig()
                        self.device_status='In Zadig, select Options → List All Devices, choose only HackRF One or RTL-SDR, and select WinUSB.'
                    elif action=='wifi_list':
                        result=self.wifi_tool('--list')
                        data=json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
                        if result.returncode or data.get('status')=='error':raise ValueError(data.get('error','Npcap was not found.'))
                        self.wifi_adapters=data.get('adapters',[]);self.remote_status=f"Found {len(self.wifi_adapters)} Npcap adapter(s)."
                    elif action=='remote_on':
                        if self.policy=='demo':
                            self.remote_status='Select Stop to leave demo mode first.'
                        elif self.config['wifi_backend']=='npcap' and not self.config['wifi_adapter']:
                            self.remote_status='Select an Npcap adapter and save the settings.'
                        else:
                            self.stop_process(self.wifi)
                            self.remote_status='Starting Wi-Fi Remote ID'
                            command=[sys.executable,str(ROOT/'wsl_wifi.py'),'--capture'] if self.config['wifi_backend']=='wsl' else [sys.executable,str(ROOT/'wifi_rid_worker.py'),*(['--wlan-scan'] if self.config['wifi_backend']=='windows' else [self.config['wifi_adapter']])]
                            try:self.wifi=self.spawn(command,self.received_remote)
                            except OSError as error:self.remote_status=str(error);self.wifi=None
                    elif action=='remote_off':
                        self.stop_process(self.wifi);self.wifi=None;self.remote_status='Wi-Fi Remote ID inactive'
                    elif action=='wifi_check':
                        if self.config['wifi_backend']=='wsl':
                            self.refresh_wifi();self.remote_status=self.wifi_reason;continue
                        if self.config['wifi_backend']=='npcap' and not self.config['wifi_adapter']:raise ValueError('Select and save an Npcap adapter.')
                        result=self.wifi_tool('--check-wlan') if self.config['wifi_backend']=='windows' else self.wifi_tool('--check',self.config['wifi_adapter'])
                        data=json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else {}
                        if result.returncode:self.remote_status=data.get('error','The check failed.')
                        elif self.config['wifi_backend']=='windows':self.remote_status='Windows WLAN scanning available · '+str(len(data.get('interfaces',[])))+' adapter(s)'
                        else:self.remote_status='Raw 802.11 available · linktype '+str(data.get('linktype'))
                    elif action=='alfa_driver_setup':
                        if value not in ('awus036h','awus036acs'):raise ValueError('Unknown Alfa model.')
                        inf=ROOT/'vendor/drivers/alfa'/value/('Netrtuw.inf' if value=='awus036h' else 'netrtwlanu.inf')
                        if not inf.exists():raise ValueError('The Alfa driver package is missing.')
                        if os.name!='nt':raise ValueError('Driver installation is supported only on Windows.')
                        result=ctypes.windll.shell32.ShellExecuteW(None,'runas','pnputil.exe',f'/add-driver "{inf}" /install',str(ROOT),0)
                        if result<=32:raise OSError('The driver installer did not open.')
                        self.remote_status='Driver installation requested for '+value.upper()+'. After completion, check the adapters again.'
                    elif action=='wsl_host_setup':
                        script=ROOT/'wsl/setup.ps1';result=ctypes.windll.shell32.ShellExecuteW(None,'runas','powershell.exe',f'-NoProfile -ExecutionPolicy Bypass -File "{script}" -Stage Host',str(ROOT),1)
                        if result<=32:raise OSError('The usbipd-win installer did not open.')
                        self.remote_status='The usbipd-win/WSL update installer opened.'
                    elif action=='wsl_bind':
                        busid=self.config['wsl_busid']
                        if not busid:raise ValueError('Enter and save the USB BUSID.')
                        script=ROOT/'wsl/setup.ps1';result=ctypes.windll.shell32.ShellExecuteW(None,'runas','powershell.exe',f'-NoProfile -ExecutionPolicy Bypass -File "{script}" -Stage Bind -BusId "{busid}"',str(ROOT),1)
                        if result<=32:raise OSError('USB binding did not start.')
                        self.remote_status='USB sharing was requested for WSL2.'
                    elif action=='wsl_attach':
                        busid=self.config['wsl_busid']
                        if not busid:raise ValueError('Enter and save the USB BUSID.')
                        result=subprocess.run(['usbipd.exe','attach','--wsl','--busid',busid],capture_output=True,text=True,timeout=30,creationflags=NO_WINDOW)
                        if result.returncode:raise ValueError(result.stderr.strip() or 'WSL USB attachment failed.')
                        self.remote_status='The Alfa adapter is attached to WSL2 and is unavailable to Windows.';self.refresh_wifi()
                    elif action=='wsl_detach':
                        busid=self.config['wsl_busid']
                        if not busid:raise ValueError('Enter and save the USB BUSID.')
                        subprocess.run(['usbipd.exe','detach','--busid',busid],capture_output=True,text=True,timeout=20,creationflags=NO_WINDOW)
                        self.remote_status='The Alfa adapter was detached from WSL2.';self.refresh_wifi()
                    elif action=='wsl_driver_setup':
                        script=ROOT/'wsl/setup-rtl8811au.sh';linux='/mnt/'+script.drive[0].lower()+str(script).replace('\\','/')[2:]
                        result=ctypes.windll.shell32.ShellExecuteW(None,'open','wsl.exe',f'-d Ubuntu-22.04 -u root -- bash "{linux}"',str(ROOT),1)
                        if result<=32:raise OSError('The WSL2 driver installer did not open.')
                        self.remote_status='RTL8811AU installation opened in WSL2.'
                    elif action=='clear_background':
                        (ROOT/'data/background.image').unlink(missing_ok=True);self.event('The custom background was removed.')
                    elif action=='map_download':
                        if self.map_download and self.map_download.poll() is None:raise ValueError('A map download is already in progress.')
                        lat,lon,radius=value['latitude'],value['longitude'],value['radius']
                        if not -85<=lat<=85 or not -180<=lon<=180 or radius not in (50,100,200):raise ValueError('Invalid map region.')
                        tool=ROOT/'map_downloader.py'
                        if not tool.exists():raise ValueError('The map download tool is missing from the package.')
                        # Keep the selected region across page/application restarts.
                        self.config['map_latitude']=lat
                        self.config['map_longitude']=lon
                        path=ROOT/'config.json';temp=path.with_suffix('.tmp')
                        temp.write_text(json.dumps(self.config,indent=2),'utf-8');temp.replace(path)
                        self.map_download_status='Starting offline map download…'
                        self.map_download=self.spawn([sys.executable,str(tool),str(lat),str(lon),str(radius)],self.received_map)
                    elif action in ('auto', 'adsb', 'ais', 'acars','vdl2','hfdl','sonde','stop', 'demo'):
                        was_demo = self.policy == 'demo'
                        self.policy = 'stopped' if action == 'stop' else action
                        self.error = ''
                        if was_demo or action == 'demo':
                            self.tracks.clear()
                        if action in ('stop', 'demo'):
                            self.mode = action
                            self.stop_process(self.radio)
                            self.stop_process(self.bridge)
                            self.radio = self.bridge = None
                            self.stop_process(self.wifi);self.wifi=None;self.remote_status='Wi-Fi Remote ID inactive'
                            self.schedule.deadline = None
                            self.event('Demo — synthetic data' if action == 'demo' else 'Reception stopped.')
                        else:
                            self.rtl_selected_serial = ''
                            if self.config['receiver_type']=='wifi':
                                if action!='auto':raise ValueError('Wi-Fi-only mode supports Remote ID through Automatic cycle.')
                                self.refresh_wifi()
                                if not self.wifi_available:raise ValueError(self.wifi_reason)
                                if not self.config['wifi_enabled']:raise ValueError('Enable Wi-Fi Remote ID in Scanning options first.')
                                self.mode='wifi';self.schedule.deadline=None
                            else:
                                first='adsb' if self.schedule.adsb else self.schedule.next()
                                self.switch(first if action=='auto' else action)
                            if action=='auto' and self.config['wifi_enabled'] and self.wifi_available:
                                self.stop_process(self.wifi);command=[sys.executable,str(ROOT/'wsl_wifi.py'),'--capture'] if self.config['wifi_backend']=='wsl' else [sys.executable,str(ROOT/'wifi_rid_worker.py'),*(['--wlan-scan'] if self.config['wifi_backend']=='windows' else [self.config['wifi_adapter']])]
                                self.wifi=self.spawn(command,self.received_remote)
                                self.remote_status='Wi-Fi Remote ID active'
                    if self.policy == 'demo':
                        self.demo()
                    elif self.policy in ('auto', 'adsb', 'ais','acars','vdl2','hfdl','sonde'):
                        if self.radio and self.radio.poll() is not None:
                            message=self.decoder_error(self.radio,'HackRF' if self.config['receiver_type']=='hackrf' else 'RTL-SDR')
                            if self.config['receiver_type']=='rtl' and message.startswith('RTL-SDR was found'):
                                self.launch_zadig(automatic=True)
                                message+=' Zadig opened automatically.'
                            raise RuntimeError(message)
                        if self.mode == 'adsb' and self.bridge and self.bridge.poll() is not None:
                            raise RuntimeError('The VRS bridge stopped unexpectedly. Check data/radar.log.')
                        if self.schedule.due(time.monotonic()) and self.policy in ('auto', 'ais'):
                            if self.policy == 'ais':
                                self.policy = 'auto'
                            self.switch(self.schedule.next())
                    if self.wifi and self.wifi.poll() is not None:
                        self.remote_status='Wi-Fi capture stopped. Check Npcap, monitor mode, and data/radar.log.'
                        self.wifi=None
                except Exception as error:
                    self.error = str(error)
                    self.event(self.error)
                    self.policy = 'stopped'
                    self.mode = 'error'
                    self.schedule.deadline = None
                    self.stop_process(self.radio)
                    self.stop_process(self.bridge)
                    self.radio = self.bridge = None
        finally:
            self.stop_process(self.radio)
            self.stop_process(self.bridge)
            self.stop_process(self.wifi)

    def demo(self):
        t = time.time()
        base_lat=self.config['map_latitude'];base_lon=self.config['map_longitude']
        for i, (lat, lon) in enumerate(((base_lat+.35,base_lon+.4),(base_lat-.4,base_lon-.5),(base_lat+.65,base_lon-.45))):
            self.tracks.update('aircraft', 'DEMO' + str(i), {
                'lat': lat + math.sin(t / 180 + i) * .15,
                'lon': lon + math.cos(t / 180 + i) * .2,
                'name': 'DEMO AIR ' + str(i + 1), 'speed': 420, 'altitude': 28000 + i * 2000,
                'course': (t / 3 + i * 100) % 360, 'source': 'SYNTHETIC'}, t)
        for i, (lat, lon) in enumerate(((base_lat+.25,base_lon+.3),(base_lat-.1,base_lon+.5),(base_lat-.55,base_lon-.15))):
            self.tracks.update('vessel', 'DEMO' + str(i), {'lat': lat, 'lon': lon,
                'name': 'DEMO SEA ' + str(i + 1), 'speed': 14, 'course': 135,
                'source': 'SYNTHETIC'}, t)
        self.tracks.update('sonde','DEMO-RS41',{'lat':base_lat+.4,'lon':base_lon+.15,'name':'DEMO RS41','altitude':18000,'source':'SYNTHETIC'},t)
        self.tracks.update('drone','DEMO-DRONE',{'lat':base_lat+.12,'lon':base_lon+.17,'name':'DEMO DRONE','altitude':150,'source':'SYNTHETIC'},t)

    def state(self):
        with self.lock:
            remaining = None
            if self.schedule.deadline is not None and self.policy in ('auto', 'ais'):
                remaining = max(0, math.ceil(self.schedule.deadline - time.monotonic()))
            cycle=[{'mode':mode,'seconds':self.schedule.seconds[mode]} for mode in self.schedule.cycle()]
            return {'mode': self.mode, 'policy': self.policy, 'remaining': remaining, 'cycle':cycle,
                    'error': self.error, 'config': dict(self.config), 'token': self.token,
                    'tracks': self.tracks.snapshot(), 'events': list(self.events),
                    'last_message': dict(self.last_message), 'counts': dict(self.counts),
                    'messages':list(self.messages),'remote_status':self.remote_status,'wifi_adapters':self.wifi_adapters,
                    'has_background':(ROOT/'data/background.image').exists(),'device_status':self.device_status,
                    'wifi_available':self.wifi_available,'wifi_active':bool(self.wifi and self.wifi.poll() is None),
                    'wifi_interfaces':list(self.wifi_interfaces),
                    'wifi_hardware':self.wifi_hardware,
                    'wifi_reason':self.wifi_reason,'map_download_status':self.map_download_status,
                    'dependencies':self.dependencies(),
                    'version':'0.10.1',
                    'map_revision':(ROOT/'maps/satellite.json').stat().st_mtime_ns if (ROOT/'maps/satellite.json').exists() else 0,
                    'time': time.time()}

    def close(self):
        self.done.set()
        self.thread.join(timeout=10)
        self.job.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def allowed(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def send(self, status, data, mime='application/json; charset=utf-8'):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if not self.allowed():
            return self.send(403, {'error': 'Host rejected'})
        clean_path=self.path.split('?',1)[0]
        if clean_path == '/api/state':
            return self.send(200, self.server.controller.state())
        if clean_path == '/user-background':
            try:
                data=(ROOT/'data/background.image').read_bytes()
                mime='image/png' if data.startswith(b'\x89PNG') else 'image/webp' if data.startswith(b'RIFF') and data[8:12]==b'WEBP' else 'image/jpeg'
                return self.send(200,data,mime)
            except FileNotFoundError:return self.send(404,{'error':'No background has been configured.'})
        tile = re.fullmatch(r'/tiles/(\d{1,2})/(\d{1,5})/(\d{1,5})\.jpg', self.path)
        if tile:
            database = ROOT / 'maps/satellite.sqlite'
            if database.exists():
                with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
                    row = db.execute('SELECT data FROM tiles WHERE z=? AND x=? AND y=?',
                                     tuple(map(int, tile.groups()))).fetchone()
                if row:
                    return self.send(200, row[0], 'image/jpeg')
            return self.send(404, {'error': 'Tile not packaged'})
        routes = {'/': ('web/index.html', 'text/html; charset=utf-8'),
                  '/app.js': ('web/app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('web/style.css', 'text/css; charset=utf-8'),
                  '/land.json': ('maps/land.json', 'application/json')}
        routes['/satellite.json'] = ('maps/satellite.json', 'application/json')
        routes['/places.json'] = ('maps/places.json', 'application/json')
        routes['/update_logic.js'] = ('web/update_logic.js', 'text/javascript; charset=utf-8')
        if self.path not in routes:
            return self.send(404, {'error': 'Not found'})
        path, mime = routes[self.path]
        try:
            self.send(200, (ROOT / path).read_bytes(), mime)
        except FileNotFoundError:
            self.send(503, {'error': 'Missing packaged asset: ' + path})

    def do_POST(self):
        c = self.server.controller
        if not self.allowed() or not secrets.compare_digest(self.headers.get('X-Radar-Token', ''), c.token):
            return self.send(403, {'error': 'Rejected'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if self.path=='/api/background':
                if not 0<length<=10_000_000:raise ValueError('The image must be no larger than 10 MB.')
                mime=self.headers.get('Content-Type','').split(';')[0]
                data=self.rfile.read(length)
                valid=(mime=='image/jpeg' and data[:3]==b'\xff\xd8\xff') or (mime=='image/png' and data[:8]==b'\x89PNG\r\n\x1a\n') or (mime=='image/webp' and data[:4]==b'RIFF' and data[8:12]==b'WEBP')
                if not valid:raise ValueError('Select a valid JPEG, PNG, or WebP image.')
                path=ROOT/'data/background.image';temp=path.with_suffix('.tmp');temp.write_bytes(data);temp.replace(path)
                c.event('The custom background was saved.');return self.send(200,{'ok':True})
            if not 0 < length <= 4096:
                raise ValueError('Invalid body size')
            obj = json.loads(self.rfile.read(length))
            if self.path == '/api/command' and obj['action'] in ('auto','remote_on','remote_off','wifi_list','wifi_check','alfa_driver_setup','wsl_host_setup','wsl_bind','wsl_attach','wsl_detach','wsl_driver_setup','clear_background','device_check','driver_setup','stop','demo'):
                c.command(obj['action'],obj.get('model'))
            elif self.path=='/api/map-download':
                c.command('map_download',{'latitude':float(obj['latitude']),'longitude':float(obj['longitude']),'radius':int(obj['radius'])})
            elif self.path == '/api/config':
                required = ('station_name','wifi_model','wifi_backend','wifi_adapter','wsl_busid','latitude','longitude','map_latitude','map_longitude','adsb_seconds','ais_seconds','device_index','ppm','receiver_type','hackrf_serial','hackrf_lna','hackrf_vga','hackrf_amp','scan')
                cfg = validate_config({**c.config,**{key: obj[key] for key in required},
                                       'rtl_serial': obj.get('rtl_serial', c.config.get('rtl_serial', ''))})
                if c.policy != 'stopped':
                    raise ValueError('Select Stop before changing settings.')
                c.command('config', cfg)
            elif self.path=='/api/protocols':
                if c.policy!='stopped':raise ValueError('Select Stop before changing settings.')
                cfg=validate_config({**c.config,'protocols':obj['protocols'],'scan':obj['scan'],'wifi_enabled':bool(obj['wifi_enabled']) and c.wifi_available})
                c.command('config',cfg)
            elif self.path == '/api/exit':
                self.send(200, {'ok': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            else:
                return self.send(404, {'error': 'Not found'})
            self.send(202, {'ok': True})
        except (ValueError, KeyError, TypeError) as error:
            self.send(400, {'error': str(error)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args()
    mutex = None
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        mutex = kernel.CreateMutexW(None, False, 'Local\\RFTrafficMonitorOneSDR')
        if not mutex or ctypes.get_last_error() == 183:
            raise RuntimeError('RF Traffic Monitor is already running. Open http://127.0.0.1:8787')
    (ROOT / 'data').mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(ROOT / 'data/radar.log',
                        maxBytes=2_000_000, backupCount=2, encoding='utf-8')],
                        format='%(asctime)s %(message)s')
    # Bind before starting children: a second instance cannot claim the receiver.
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    controller = Controller()
    server.controller = controller
    url = f'http://127.0.0.1:{args.port}'
    print('RF Traffic Monitor — ' + url + '\nCtrl+C to exit.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        controller.close()
        server.server_close()
        if mutex:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(mutex)


if __name__ == '__main__':
    main()
