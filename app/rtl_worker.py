"""One V3 device -> offline native DSP child, both owned by controller's Job."""
import ctypes as C
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent

def main():
    mode,index,ppm,channels=sys.argv[1:]
    frequencies=[int(x) for x in channels.split(',')]
    center=(min(frequencies)+max(frequencies))//2
    rate=1200000 if max(frequencies)-min(frequencies)>180000 else 240000
    folder=ROOT/'vendor/native'
    dll_dir=os.add_dll_directory(str(folder))
    rtl=C.CDLL(str(folder/'rtlsdr.dll'))
    device=C.c_void_p()
    for name,args in {
        'rtlsdr_open':[C.POINTER(C.c_void_p),C.c_uint32],
        'rtlsdr_set_sample_rate':[C.c_void_p,C.c_uint32],
        'rtlsdr_set_center_freq':[C.c_void_p,C.c_uint32],
        'rtlsdr_set_freq_correction':[C.c_void_p,C.c_int],
        'rtlsdr_set_direct_sampling':[C.c_void_p,C.c_int],
        'rtlsdr_set_tuner_gain_mode':[C.c_void_p,C.c_int],
        'rtlsdr_set_bias_tee':[C.c_void_p,C.c_int],
        'rtlsdr_reset_buffer':[C.c_void_p],
        'rtlsdr_close':[C.c_void_p],
        'rtlsdr_read_sync':[C.c_void_p,C.c_void_p,C.c_int,C.POINTER(C.c_int)],
    }.items():getattr(rtl,name).argtypes=args
    def check(code):
        if code<0:raise RuntimeError(f'RTL-SDR error {code}; check V3, WinUSB, device index')
    check(rtl.rtlsdr_open(C.byref(device),int(index)))
    decoder=None
    try:
        check(rtl.rtlsdr_set_bias_tee(device,0))
        check(rtl.rtlsdr_set_direct_sampling(device,2 if mode=='hfdl' else 0))
        check(rtl.rtlsdr_set_sample_rate(device,rate))
        # librtlsdr returns -2 when no correction change is needed.
        correction=rtl.rtlsdr_set_freq_correction(device,int(ppm))
        if correction!=-2:check(correction)
        if mode!='hfdl':check(rtl.rtlsdr_set_tuner_gain_mode(device,0))
        check(rtl.rtlsdr_set_center_freq(device,center))
        check(rtl.rtlsdr_reset_buffer(device))
        decoder=subprocess.Popen([str(folder/'radar-decode.exe'),mode,str(rate),str(center),channels,'u8'],
            stdin=subprocess.PIPE,stdout=sys.stdout,stderr=sys.stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        print(json.dumps({'status':'receiving','protocol':mode}),flush=True)
        buffer=C.create_string_buffer(65536);read=C.c_int()
        while decoder.poll() is None:
            check(rtl.rtlsdr_read_sync(device,buffer,len(buffer),C.byref(read)))
            if read.value<=0:raise RuntimeError('RTL-SDR returned no samples')
            decoder.stdin.write(buffer.raw[:read.value]);decoder.stdin.flush()
        raise RuntimeError('Native DSP decoder exited')
    finally:
        if decoder and decoder.poll() is None:decoder.kill();decoder.wait()
        rtl.rtlsdr_close(device)
        dll_dir.close()

if __name__=='__main__':main()
