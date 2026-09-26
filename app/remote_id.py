"""Decode ASTM/OpenDroneID transport payloads without inferring a location."""
import base64
import ctypes as C
import re
import time
from pathlib import Path

class RemoteID:
    def __init__(self,tracks):
        self.tracks=tracks;self.names={};self.stamps={};self.decoder=None;self.validated=False

    def ingest(self,msg,now=None):
        self.validated=False
        now=time.time() if now is None else now
        address=msg.get('address','')
        if not re.fullmatch('[0-9A-F]{12}',address):return 0
        try:raw=base64.b64decode(msg.get('data',''),validate=True)
        except (ValueError,TypeError):return 0
        if raw[:3]!=b'\xfa\xff\x0d' or len(raw)<29:return 0
        raw=raw[4:] # UUID, app code, advertisement counter
        if raw[0]>>4==15:
            if len(raw)<3 or raw[1]!=25 or not 1<=raw[2]<=9 or len(raw)!=3+25*raw[2]:return 0
            messages=[raw[i:i+25] for i in range(3,len(raw),25)]
        elif len(raw)==25:messages=[raw]
        else:return 0
        self.validated=True
        if self.decoder is None:
            self.decoder=C.CDLL(str(Path(__file__).parent/'vendor/native/rid_decode.dll'))
            self.decoder.rid_decode.argtypes=[C.c_void_p,C.c_int,C.POINTER(C.c_double),C.c_char_p]
        count=0
        for packet in messages:
            vals=(C.c_double*7)();ident=C.create_string_buffer(21)
            kind=self.decoder.rid_decode(packet,25,vals,ident)
            if kind==0:
                name=ident.value.decode('ascii','replace')
                if name:self.names[address]=(name,now)
                continue
            if kind!=1 or not (-90<=vals[0]<=90 and -180<=vals[1]<=180) or (vals[0]==0 and vals[1]==0):continue
            # Duplicate location advertisements must not refresh the position age.
            fingerprint=packet
            if self.stamps.get(address,(None,0))[0]==fingerprint:continue
            self.stamps[address]=(fingerprint,now)
            name=self.names.get(address,(address,now))[0]
            self.tracks.update('drone',address,{'name':name,'lat':vals[0],'lon':vals[1],
                'altitude':vals[2]*3.28084 if vals[2]!=-1000 else None,
                'speed':vals[3]*1.943844 if vals[3]!=255 else None,
                'course':vals[4] if vals[4]<360 else None,
                'source':'Remote ID / Wi-Fi' if msg.get('transport')=='wifi' else 'Remote ID',
                'rssi':msg.get('rssi'),'verified':False},now);count+=1
        self.names={k:v for k,v in self.names.items() if now-v[1]<600}
        self.stamps={k:v for k,v in self.stamps.items() if now-v[1]<600}
        return count

    def ingest_wifi(self,msg,now=None):
        """Accept the OpenDroneID bytes following the Wi-Fi vendor OUI/type."""
        try:payload=base64.b64decode(msg.get('data',''),validate=True)
        except (ValueError,TypeError):return 0
        wrapped={**msg,'data':base64.b64encode(b'\xfa\xff\x0d\x00'+payload).decode()}
        return self.ingest(wrapped,now)
