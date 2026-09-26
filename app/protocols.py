"""Configuration and strict adapters for the four offline DSP cores."""
import copy
import json
import time
from model import number

DEFAULTS={
    'acars':{'enabled':True,'seconds':15,'frequencies':[131550000,131725000,131825000]},
    'vdl2':{'enabled':True,'seconds':15,'frequencies':[136975000]},
    'hfdl':{'enabled':False,'seconds':15,'frequencies':[10081000]},
    'sonde':{'enabled':False,'seconds':15,'frequencies':[403000000]},
}

def validate_protocols(value):
    if value is None:return copy.deepcopy(DEFAULTS)
    if not isinstance(value,dict) or set(value)!=set(DEFAULTS):raise ValueError('Invalid protocols')
    out={}
    for mode,p in value.items():
        if not isinstance(p,dict):raise ValueError('Invalid protocol settings')
        enabled=p.get('enabled');seconds=p.get('seconds');freq=p.get('frequencies')
        lo,hi={'acars':(118000000,137000000),'vdl2':(136600000,137000000),'hfdl':(2800000,22000000),'sonde':(400000000,406000000)}[mode]
        if type(enabled)!=bool or type(seconds)!=int or not 5<=seconds<=60:raise ValueError('Interval must be 5–60 seconds')
        if not isinstance(freq,list) or not 1<=len(freq)<=8 or any(type(f)!=int or not lo<=f<=hi for f in freq):raise ValueError('Invalid frequencies for '+mode)
        if max(freq)-min(freq)>900000:raise ValueError('Channels must fit within a 900 kHz window')
        out[mode]={'enabled':enabled,'seconds':seconds,'frequencies':sorted(set(freq))}
    return out

def ingest(tracks,mode,msg,now=None):
    now=time.time() if now is None else now
    if not isinstance(msg,dict) or not msg.get('decode',{}).get('crc_ok'):return None
    b=msg.get('body',{});details=b.get('details') or {}
    ident=b.get('tail') or b.get('flight') or ''
    if mode=='sonde':
        ident=details.get('serial','')
        gps=details.get('gps_pos') or {}
        if ident and details.get('crc',{}).get('gps_pos') and gps.get('num_sv',0)>=4:
            tracks.update('sonde',ident,{'lat':gps.get('lat'),'lon':gps.get('lon'),
                'name':ident,'altitude':gps.get('alt_m',0)*3.28084,'speed':gps.get('speed_ms',0)*1.943844,
                'course':gps.get('course_deg'),'source':'RS41 / xng'},now)
    elif mode=='hfdl':
        pos=details.get('position') or {};ident=pos.get('icao') or pos.get('flight') or ident
        # Never merge GS-local 8-bit aircraft aliases with global ICAO addresses.
        stamp=recent_time(pos.get('utc_s'),now,86400)
        if ident and pos and stamp is not None and not (pos.get('lat')==0 and pos.get('lon')==0):
            tracks.update('aircraft',str(ident),{'lat':pos.get('lat'),'lon':pos.get('lon'),
                'name':pos.get('flight') or str(ident),'source':'HFDL / xng'},stamp)
    if b.get('type')=='acars':
        app=b.get('app') or {}
        if isinstance(app.get('app'),dict):app=app['app']
        if app.get('app')=='adsc' and app.get('crc_ok') and not app.get('err') and not b.get('more_to_come'):
            tags=app.get('tags',[])
            icao=next((t.get('icao') for t in tags if t.get('tag')=='airframe_id'),None)
            for tag in tags:
                if tag.get('tag')!='report' or not tag.get('accuracy'):continue
                stamp=recent_time(tag.get('timestamp_s'),now,3600)
                if (icao or ident) and stamp is not None:
                    tracks.update('aircraft',icao or 'REG:'+ident,{'name':b.get('flight') or ident,
                        'lat':tag.get('lat'),'lon':tag.get('lon'),'altitude':tag.get('alt_ft'),
                        'source':mode.upper()+' / ADS-C'},stamp)
    # Never map predicted routes or coordinates extracted from arbitrary text.
    return {'protocol':mode,'ident':str(ident),'frequency':msg.get('frequency_hz'),
            'text':json.dumps(b,ensure_ascii=False,separators=(',',':'))[:4000]}

def recent_time(seconds,now,period):
    value=number(seconds,0,period-0.001)
    if value is None:return None
    candidate=now-now%period+value
    if candidate>now+5:candidate-=period
    return min(candidate,now) if now-candidate<=180 else None
