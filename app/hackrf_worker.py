"""One HackRF -> one offline decoder. RX only; transmitter APIs are never used."""
import ctypes as C
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parent

class Transfer(C.Structure):
    _fields_=[('device',C.c_void_p),('buffer',C.POINTER(C.c_byte)),
              ('buffer_length',C.c_int),('valid_length',C.c_int),
              ('rx_ctx',C.c_void_p),('tx_ctx',C.c_void_p)]

def api():
    folder=ROOT/'vendor/ais'
    handle=os.add_dll_directory(str(folder))
    lib=C.CDLL(str(folder/'hackrf.dll'))
    lib.hackrf_init.restype=C.c_int;lib.hackrf_exit.restype=C.c_int
    lib.hackrf_open_by_serial.argtypes=[C.c_char_p,C.POINTER(C.c_void_p)]
    lib.hackrf_close.argtypes=[C.c_void_p]
    lib.hackrf_set_sample_rate.argtypes=[C.c_void_p,C.c_double]
    lib.hackrf_set_freq.argtypes=[C.c_void_p,C.c_uint64]
    lib.hackrf_set_baseband_filter_bandwidth.argtypes=[C.c_void_p,C.c_uint32]
    lib.hackrf_set_lna_gain.argtypes=[C.c_void_p,C.c_uint32]
    lib.hackrf_set_vga_gain.argtypes=[C.c_void_p,C.c_uint32]
    lib.hackrf_set_amp_enable.argtypes=[C.c_void_p,C.c_uint8]
    lib.hackrf_is_streaming.argtypes=[C.c_void_p];lib.hackrf_is_streaming.restype=C.c_int
    return lib,handle

def check(code,what):
    if code!=0:raise RuntimeError(f'HackRF {what}: error {code}; check WinUSB and the USB connection')

def open_device(lib,serial):
    check(lib.hackrf_init(),'init')
    device=C.c_void_p()
    check(lib.hackrf_open_by_serial(serial.encode('ascii') if serial else None,C.byref(device)),'open')
    return device

def main():
    lib,dll_dir=api();device=None;decoder=None
    try:
        if sys.argv[1:] == ['--check']:
            device=open_device(lib,'');print(json.dumps({'ok':True,'text':'HackRF detected'}));return
        if len(sys.argv)!=10:raise RuntimeError('usage: MODE SERIAL LNA VGA AMP PPM CHANNELS LAT LON')
        mode,serial,lna,vga,amp,ppm,channels,lat,lon=sys.argv[1:]
        frequencies=[int(x) for x in channels.split(',')]
        center=1090000000 if mode=='adsb' else (162000000 if mode=='ais' else (min(frequencies)+max(frequencies))//2)
        rate=2000000
        device=open_device(lib,serial)
        for code,name in ((lib.hackrf_set_sample_rate(device,rate),'sample rate'),
                          (lib.hackrf_set_baseband_filter_bandwidth(device,1750000),'bandwidth'),
                          (lib.hackrf_set_freq(device,round(center*(1-int(ppm)/1000000))),'frequency'),
                          (lib.hackrf_set_lna_gain(device,int(lna)),'LNA gain'),
                          (lib.hackrf_set_vga_gain(device,int(vga)),'VGA gain'),
                          (lib.hackrf_set_amp_enable(device,1 if amp=='1' else 0),'RF amplifier')):check(code,name)
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        if mode=='adsb':
            command=[str(ROOT/'vendor/adsb/dump1090.exe'),'--ifile','-','--net','--net-bind-address','127.0.0.1',
                     '--net-http-port','0','--net-ri-port','0','--net-ro-port','0','--net-bi-port','0','--net-bo-port','0',
                     '--net-sbs-port','30003','--quiet','--lat',lat,'--lon',lon]
        elif mode=='ais':
            command=[str(ROOT/'vendor/ais/AIS-catcher.exe'),'-r','CS8','.','-s',str(rate),'-o','5','-M','T']
        else:
            command=[str(ROOT/'vendor/native/radar-decode.exe'),mode,str(rate),str(center),channels,'u8']
        decoder=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=sys.stdout,stderr=sys.stderr,
                                 creationflags=flags,bufsize=0)
        translate=bytes.maketrans(bytes(range(256)),bytes((x+128)&255 for x in range(256)))
        failed=[None]
        CALLBACK=C.CFUNCTYPE(C.c_int,C.POINTER(Transfer))
        def receive(ptr):
            try:
                raw=C.string_at(ptr.contents.buffer,ptr.contents.valid_length)
                decoder.stdin.write(raw if mode=='ais' else raw.translate(translate))
                return 0
            except Exception as error:
                failed[0]=error;return -1
        callback=CALLBACK(receive)
        lib.hackrf_start_rx.argtypes=[C.c_void_p,CALLBACK,C.c_void_p]
        lib.hackrf_stop_rx.argtypes=[C.c_void_p]
        check(lib.hackrf_start_rx(device,callback,None),'start RX')
        print(json.dumps({'status':'receiving','protocol':mode,'receiver':'hackrf'}),flush=True)
        stopping=threading.Event()
        threading.Thread(target=lambda:(sys.stdin.buffer.read(),stopping.set()),daemon=True).start()
        while lib.hackrf_is_streaming(device)==1 and decoder.poll() is None and not stopping.wait(.1):pass
        if stopping.is_set():return
        if failed[0]:raise RuntimeError('HackRF IQ pipe: '+str(failed[0]))
        if decoder.poll() is not None:raise RuntimeError('Decoder exited while HackRF was receiving')
        raise RuntimeError('HackRF stream stopped')
    finally:
        if device:
            try:lib.hackrf_stop_rx(device)
            except Exception:pass
        if decoder and decoder.poll() is None:decoder.kill();decoder.wait()
        if device:lib.hackrf_close(device)
        try:lib.hackrf_exit()
        except Exception:pass
        dll_dir.close()

if __name__=='__main__':main()
