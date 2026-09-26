"""Download a replaceable offline EOX satellite pyramid around a chosen centre."""
import io,json,math,os,sqlite3,sys,tempfile,time,urllib.parse,urllib.request
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent;MAPS=ROOT/'maps';WORLD=40075016.68557849

def xy(lon,lat,z):
    return ((lon+180)/360*2**z,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**z)

def jpeg(image):
    out=io.BytesIO();image.save(out,'JPEG',quality=86);return out.getvalue()

def bounds(lat,lon,radius):
    dy=radius/111.195;dx=radius/(111.195*max(.15,math.cos(math.radians(lat))))
    return max(-180,lon-dx),max(-85,lat-dy),min(180,lon+dx),min(85,lat+dy)

def fetch_block(z,x,y,size=8):
    unit=WORLD/2**z;bbox=(x*unit-WORLD/2,WORLD/2-(y+size)*unit,(x+size)*unit-WORLD/2,WORLD/2-y*unit)
    params=dict(service='WMS',version='1.1.1',request='GetMap',layers='s2cloudless-2024_3857',styles='',srs='EPSG:900913',bbox=','.join(map(str,bbox)),width=size*256,height=size*256,format='image/jpeg')
    request=urllib.request.Request('https://tiles.maps.eox.at/map?'+urllib.parse.urlencode(params),headers={'User-Agent':'RFTrafficMonitor/0.10 offline map downloader'})
    for attempt in range(3):
        try:
            data=urllib.request.urlopen(request,timeout=90).read();image=Image.open(io.BytesIO(data));image.load()
            if image.size!=(size*256,size*256):raise ValueError('Unexpected image size')
            return image.convert('RGB')
        except Exception:
            if attempt==2:raise
            time.sleep(2)

def main():
    lat,lon,radius=float(sys.argv[1]),float(sys.argv[2]),int(sys.argv[3]);region=bounds(lat,lon,radius);detail=bounds(lat,lon,min(50,radius))
    MAPS.mkdir(exist_ok=True);fd,tmp=tempfile.mkstemp(prefix='satellite-',suffix='.sqlite',dir=MAPS);os.close(fd)
    try:
        db=sqlite3.connect(tmp);db.execute('CREATE TABLE tiles(z INTEGER,x INTEGER,y INTEGER,data BLOB,PRIMARY KEY(z,x,y))')
        jobs=[]
        for z,box in ((12,region),(14,detail)):
            west,south,east,north=box;x0,y0=xy(west,north,z);x1,y1=xy(east,south,z)
            for x in range(int(x0)//8*8,int(x1)+1,8):
                for y in range(int(y0)//8*8,int(y1)+1,8):jobs.append((z,x,y))
        total=len(jobs)
        for number,(z,x,y) in enumerate(jobs,1):
            image=fetch_block(z,x,y)
            for dx in range(8):
                for dy in range(8):db.execute('INSERT OR REPLACE INTO tiles VALUES(?,?,?,?)',(z,x+dx,y+dy,jpeg(image.crop((dx*256,dy*256,(dx+1)*256,(dy+1)*256)))))
            db.commit();print(json.dumps({'status':'progress','text':f'Downloading map {number}/{total} · zoom {z}'}),flush=True)
        for source,lowest in ((12,6),(14,13)):
            for z in range(source-1,lowest-1,-1):
                parents=db.execute('SELECT DISTINCT x/2,y/2 FROM tiles WHERE z=?',(z+1,)).fetchall()
                for px,py in parents:
                    image=Image.new('RGB',(512,512),(16,31,42))
                    for cx,cy,data in db.execute('SELECT x,y,data FROM tiles WHERE z=? AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?',(z+1,px*2,px*2+1,py*2,py*2+1)):
                        image.paste(Image.open(io.BytesIO(data)),((cx%2)*256,(cy%2)*256))
                    db.execute('INSERT OR REPLACE INTO tiles VALUES(?,?,?,?)',(z,px,py,jpeg(image.resize((256,256),Image.Resampling.LANCZOS))))
                db.commit()
        levels={str(z):[a,b,c,d] for z,a,b,c,d in db.execute('SELECT z,min(x),min(y),max(x),max(y) FROM tiles GROUP BY z')};db.close()
        manifest=dict(year=2024,levels=levels,license='CC BY-NC-SA 4.0',region=list(region),detail=list(detail),center=[lat,lon],radius_km=radius,source='https://cloudless.eox.at')
        Path(tmp).replace(MAPS/'satellite.sqlite');temp=MAPS/'satellite.tmp';temp.write_text(json.dumps(manifest),'utf-8');temp.replace(MAPS/'satellite.json')
        print(json.dumps({'status':'done'}),flush=True)
    except Exception as error:
        try:Path(tmp).unlink(missing_ok=True)
        finally:print(json.dumps({'status':'error','error':str(error)}),flush=True);raise

if __name__=='__main__':main()
