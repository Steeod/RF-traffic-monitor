"""Resolve one physical RTL receiver across independently bundled SDR backends."""
import ctypes as C
import json
import os
from pathlib import Path
import re
import subprocess
import sys

NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def probe(command, seconds=2):
    """Bounded receive-only probe; always release USB before returning."""
    proc = subprocess.Popen(command, cwd=str(Path(command[0]).parent),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding='utf-8', errors='replace',
                            creationflags=NO_WINDOW)
    alive = False
    try:
        try:
            out, err = proc.communicate(timeout=seconds)
        except subprocess.TimeoutExpired:
            alive = True
            proc.terminate()
            try:
                out, err = proc.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate(timeout=3)
        return alive, out + '\n' + err
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=3)


def dump_devices(output):
    devices = {}
    for match in re.finditer(r'^[ \t]*(\d+):[^\r\n]*?,[ \t]*SN:[ \t]*([^\r\n]*)$', output, re.M):
        serial = match[2].replace('(currently selected)', '').strip()
        # Old dump1090 DLLs can print uninitialized USB strings for unusable entries.
        if serial and serial.isascii() and serial.isprintable():
            devices[int(match[1])] = {'index': int(match[1]), 'serial': serial}
    return list(devices.values())


def candidates(devices, serial='', preferred=0):
    selected = [d for d in devices if not serial or d['serial'] == serial]
    if not selected:
        raise RuntimeError('RTL-SDR serial ' + (serial or '(automatic)') +
                           ' not found by this decoder. Reconnect it and run Check receiver.')
    selected.sort(key=lambda d: (d['index'] != preferred, d['index']))
    return selected


def unique_serial(device, devices):
    serial = device['serial']
    if not serial or sum(d['serial'] == serial for d in devices) != 1:
        raise RuntimeError('RTL-SDR identity is ambiguous. Connect only one receiver or use unique serial numbers.')
    return device


def resolve(root, backend, preferred=0, serial=''):
    root = Path(root)
    if backend == 'adsb':
        exe = str(root / 'vendor/adsb/dump1090.exe')
        command = [exe, '--quiet', '--device-index', str(preferred)]
        opened, output = probe(command)
        devices = dump_devices(output)
        for device in candidates(devices, serial, preferred):
            unique_serial(device, devices)
            if device['index'] == preferred:
                ok = opened
            else:
                ok, detail = probe([exe, '--quiet', '--device-index', str(device['index'])])
                output += '\n' + detail
            if ok:
                return device
        raise RuntimeError('ADS-B: no RTL-SDR could be opened. Check WinUSB and close other SDR apps. ' + output[-700:])
    # A separate process prevents the different rtlsdr/libusb DLL builds from
    # contaminating one another's DLL loader state. ADS-B is a 32-bit executable.
    result = subprocess.run([sys.executable, str(root / 'rtl_devices.py'),
                             '--resolve', backend, serial], capture_output=True,
                            text=True, encoding='utf-8', errors='replace',
                            timeout=15, creationflags=NO_WINDOW)
    if result.returncode:
        raise RuntimeError(f'{backend}: RTL-SDR discovery failed. ' + result.stderr[-700:])
    device = json.loads(result.stdout)
    if backend == 'ais':
        ok, detail = probe([str(root / 'vendor/ais/AIS-catcher.exe'),
                            '-d', device['serial'], '-o', '0', '-gr', 'BIASTEE', 'off'])
        if not ok:
            raise RuntimeError('AIS: receiver could not start. ' + detail[-700:])
    return device


def resolve_dll(folder, serial):
    with os.add_dll_directory(str(folder)):
        rtl = C.CDLL(str(folder / 'rtlsdr.dll'))
        rtl.rtlsdr_get_device_count.argtypes = []
        rtl.rtlsdr_get_device_count.restype = C.c_uint32
        rtl.rtlsdr_get_device_usb_strings.argtypes = [C.c_uint32, C.c_void_p, C.c_void_p, C.c_void_p]
        rtl.rtlsdr_open.argtypes = [C.POINTER(C.c_void_p), C.c_uint32]
        rtl.rtlsdr_close.argtypes = [C.c_void_p]
        devices = []
        for index in range(rtl.rtlsdr_get_device_count()):
            manufacturer, product, number = (C.create_string_buffer(256) for _ in range(3))
            if rtl.rtlsdr_get_device_usb_strings(index, manufacturer, product, number) == 0:
                devices.append({'index': index, 'serial': number.value.decode('utf-8', errors='replace')})
        for device in candidates(devices, serial):
            unique_serial(device, devices)
            handle = C.c_void_p()
            if rtl.rtlsdr_open(C.byref(handle), device['index']) == 0:
                try:
                    return device
                finally:
                    rtl.rtlsdr_close(handle)
        raise RuntimeError('No RTL-SDR could be opened. Check WinUSB and close other SDR apps.')


if __name__ == '__main__':
    try:
        _, backend, serial = sys.argv[1:]
        if backend not in ('ais', 'native'):
            raise ValueError('Unknown RTL backend')
        print(json.dumps(resolve_dll(Path(__file__).resolve().parent / 'vendor' / backend, serial)))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
