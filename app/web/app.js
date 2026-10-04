'use strict';
const $ = id => document.getElementById(id);
const canvas = $('map'), ctx = canvas.getContext('2d');
let clientError = '', mapRevision = null, mapRefreshPending = false;
function showError(message){clientError=message;$('error').hidden=false;$('error').textContent=message;}
let state = null, land = [], selected = null, cfgLoaded = false, receivedAt = 0;
const receiverSelect=$('settings').elements.receiver_type;
if(!receiverSelect.querySelector('option[value="wifi"]'))receiverSelect.add(new Option('Wi-Fi Remote ID only','wifi'));
receiverSelect.querySelector('option[value="rtl"]').textContent='RTL-SDR (primary SDR)';
receiverSelect.querySelector('option[value="hackrf"]').textContent='HackRF One (primary SDR)';
receiverSelect.querySelector('option[value="wifi"]').textContent='No SDR — Wi-Fi Remote ID only';
receiverSelect.closest('label').firstChild.textContent='Primary SDR receiver';
$('wifi-scan-label').lastChild.textContent=' Parallel Wi-Fi receiver · Remote ID';
const creatorCredit=document.createElement('span');creatorCredit.className='map-creator';creatorCredit.textContent=' · RF Traffic Monitor · Made by Steeod';document.querySelector('.attribution').append(creatorCredit);
let view = {lat:0,lon:0,scale:1}, hit = [], width=1, height=1, mapBounds={west:-4,east:4,south:-3.5,north:3.5};
const fmt=(x,unit='')=>x==null?'—':Math.round(x).toLocaleString('en-US')+unit;
const ageText=x=>x<60?Math.floor(x)+' s':Math.floor(x/60)+' min';
function currentAge(t){return t.age+(Date.now()-receivedAt)/1000;}
const kinds={aircraft:{filter:'air-filter',color:'#f2b964',icon:'✈',stale:15},vessel:{filter:'sea-filter',color:'#54ccc1',icon:'▰',stale:180},sonde:{filter:'sonde-filter',color:'#bda0ff',icon:'◉',stale:120},drone:{filter:'drone-filter',color:'#ff86b5',icon:'✣',stale:10}};
function stale(t){return currentAge(t)>kinds[t.kind].stale;}
function visible(){const q=$('search').value.toUpperCase();return (state?.tracks||[]).filter(t=>kinds[t.kind]&&$(kinds[t.kind].filter).checked&&((t.name||'')+t.ident).toUpperCase().includes(q));}
const mercY=lat=>(1-Math.asinh(Math.tan(lat*Math.PI/180))/Math.PI)/2;
const worldSize=()=>Math.min(width,height)/480*view.scale*40075.0167*Math.cos(view.lat*Math.PI/180);
function project(lat,lon){const s=worldSize();return [width/2+(lon-view.lon)/360*s,height/2+(mercY(lat)-mercY(view.lat))*s];}
let satellite=null, satelliteOn=true;
let places=[];
function drawPlaces(){
 const occupied=[],zoom=Math.log2(worldSize()/256);
 const minZoom={city:6,town:7,village:8.3,hamlet:10,suburb:10.5,neighbourhood:12};
 const labels=places;
 for(const p of labels){
  if(zoom<(minZoom[p.kind]||8))continue;
  const [x,y]=project(p.lat,p.lon);
  if(x<5||x>width-5||y<15||y>height-85)continue;
  ctx.font=(p.kind==='city'?'bold 12':'11')+'px Segoe UI';
  const w=ctx.measureText(p.name).width,box=[x-w/2-5,y-17,x+w/2+5,y+5];
  if(occupied.some(b=>box[0]<b[2]&&box[2]>b[0]&&box[1]<b[3]&&box[3]>b[1]))continue;
  occupied.push(box);ctx.textAlign='center';ctx.lineWidth=3.5;ctx.strokeStyle='#101820';
  ctx.strokeText(p.name,x,y-5);ctx.fillStyle='#eef2e7';ctx.fillText(p.name,x,y-5);
  ctx.beginPath();ctx.arc(x,y+1,1.7,0,Math.PI*2);ctx.fill();
 }
}
const tileCache=new Map();
function drawSatellite(){
 if(!satellite||!satelliteOn)return;
 const s=worldSize(),cx=(view.lon+180)/360,cy=mercY(view.lat);
 const top=Math.min(14,Math.max(6,Math.ceil(Math.log2(s/256))));
 for(let z=6;z<=top;z++){
  const bounds=satellite.levels[z];if(!bounds)continue;
  const n=2**z,size=s/n;
  const x0=Math.max(bounds[0],Math.floor((cx-width/2/s)*n)),x1=Math.min(bounds[2],Math.floor((cx+width/2/s)*n));
  const y0=Math.max(bounds[1],Math.floor((cy-height/2/s)*n)),y1=Math.min(bounds[3],Math.floor((cy+height/2/s)*n));
  for(let x=x0;x<=x1;x++)for(let y=y0;y<=y1;y++){
   const key=`${z}/${x}/${y}`;let im=tileCache.get(key);
   if(!im){im=new Image();tileCache.set(key,im);im.onload=()=>requestAnimationFrame(draw);im.src=`/tiles/${key}.jpg`;}
   if(im.complete&&im.naturalWidth)ctx.drawImage(im,width/2+(x/n-cx)*s,height/2+(y/n-cy)*s,size+.5,size+.5);
  }
 }
 while(tileCache.size>700){const key=tileCache.keys().next().value;tileCache.delete(key);}
}
function path(points){points.forEach(([lat,lon],i)=>{const [x,y]=project(lat,lon);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});}
function draw(){
 width=canvas.clientWidth;height=canvas.clientHeight;const dpr=devicePixelRatio||1;
 if(canvas.width!==Math.round(width*dpr)||canvas.height!==Math.round(height*dpr)){canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);}
 ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);ctx.fillStyle='#101f2a';ctx.fillRect(0,0,width,height);
 ctx.lineWidth=1;ctx.strokeStyle='#1b303c';ctx.font='10px Segoe UI';ctx.fillStyle='#456272';
 const span=Math.max(mapBounds.east-mapBounds.west,mapBounds.north-mapBounds.south),grid=span>20?5:span>8?2:span>4?1:.5;
 for(let lat=Math.ceil(mapBounds.south/grid)*grid;lat<=mapBounds.north;lat+=grid){let a=project(lat,mapBounds.west),b=project(lat,mapBounds.east);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();ctx.fillText(lat.toFixed(grid<1?1:0)+'°',8,a[1]-5);}
 for(let lon=Math.ceil(mapBounds.west/grid)*grid;lon<=mapBounds.east;lon+=grid){let a=project(mapBounds.south,lon),b=project(mapBounds.north,lon);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();}
 ctx.fillStyle='#23383f';ctx.strokeStyle='#4c686d';ctx.lineWidth=.85;
 for(const polygon of land){ctx.beginPath();for(const ring of polygon){ring.forEach(([lon,lat],i)=>{const p=project(lat,lon);i?ctx.lineTo(...p):ctx.moveTo(...p);});ctx.closePath();}ctx.fill('evenodd');ctx.stroke();}
 drawSatellite();
 const station=state?.config||{latitude:0,longitude:0};
 ctx.strokeStyle='#4c727c';ctx.lineWidth=.8;ctx.setLineDash([4,7]);
 for(const radius of [50,100,200]){ctx.beginPath();for(let i=0;i<=120;i++){let bearing=i/120*Math.PI*2,angle=radius/6371,phi=station.latitude*Math.PI/180,lambda=station.longitude*Math.PI/180;let lat=Math.asin(Math.sin(phi)*Math.cos(angle)+Math.cos(phi)*Math.sin(angle)*Math.cos(bearing));let lon=lambda+Math.atan2(Math.sin(bearing)*Math.sin(angle)*Math.cos(phi),Math.cos(angle)-Math.sin(phi)*Math.sin(lat));let p=project(lat*180/Math.PI,lon*180/Math.PI);i?ctx.lineTo(...p):ctx.moveTo(...p);}ctx.stroke();let p=project(station.latitude+radius/111.195,station.longitude);ctx.fillStyle='#819ea6';ctx.fillText(radius+' km',p[0]+5,p[1]-6);}
 ctx.setLineDash([]);ctx.textAlign='center';
 drawPlaces();
 const p=project(station.latitude,station.longitude);ctx.strokeStyle='#7cdbd2';ctx.beginPath();ctx.arc(...p,7,0,Math.PI*2);ctx.stroke();ctx.fillStyle='#7cdbd2';ctx.beginPath();ctx.arc(...p,2,0,Math.PI*2);ctx.fill();
 hit=[];
 for(const t of visible()){
  const [x,y]=project(t.lat,t.lon),old=stale(t),color=kinds[t.kind].color;
  ctx.globalAlpha=old?.35:1;
  if($('trails').checked&&t.trail.length>1){ctx.beginPath();path(t.trail);ctx.strokeStyle=color;ctx.lineWidth=t.id===selected?2:1;ctx.stroke();}
  if(x<-30||x>width+30||y<-30||y>height+30)continue;
  if(t.id===selected){ctx.beginPath();ctx.arc(x,y,18,0,Math.PI*2);ctx.strokeStyle='#ffffff';ctx.lineWidth=1;ctx.stroke();}
  ctx.save();ctx.translate(x,y);ctx.rotate((t.course||0)*Math.PI/180);ctx.beginPath();
  if(t.kind==='aircraft'){ctx.moveTo(0,-12);ctx.lineTo(3,-4);ctx.lineTo(12,3);ctx.lineTo(12,5);ctx.lineTo(3,2);ctx.lineTo(3,8);ctx.lineTo(6,11);ctx.lineTo(0,9);ctx.lineTo(-6,11);ctx.lineTo(-3,8);ctx.lineTo(-3,2);ctx.lineTo(-12,5);ctx.lineTo(-12,3);ctx.lineTo(-3,-4);}
  else if(t.kind==='sonde'){ctx.arc(0,-3,7,0,Math.PI*2);ctx.moveTo(-2,3);ctx.lineTo(0,13);ctx.lineTo(2,3);}
  else if(t.kind==='drone'){for(const [a,b] of [[-6,-6],[6,-6],[-6,6],[6,6]]){ctx.moveTo(a+4,b);ctx.arc(a,b,4,0,Math.PI*2);}ctx.rect(-2,-8,4,16);ctx.rect(-8,-2,16,4);}
  else{ctx.moveTo(0,-10);ctx.lineTo(5,-3);ctx.lineTo(5,8);ctx.lineTo(-5,8);ctx.lineTo(-5,-3);}
  ctx.closePath();ctx.fillStyle=color;ctx.fill();ctx.restore();ctx.font='11px Segoe UI';ctx.textAlign='left';ctx.fillStyle=color;ctx.fillText(t.name||t.ident,x+16,y-3);ctx.fillStyle='#9db1bd';ctx.font='10px Segoe UI';ctx.fillText(ageText(currentAge(t)),x+16,y+11);hit.push({id:t.id,x,y});
 }
 ctx.globalAlpha=1;ctx.textAlign='left';
 const k=Math.min(width,height)/480*view.scale;
 const km=[.1,.2,.5,1,2,5,10,20,50,100].filter(n=>n*k<=110).pop()||.1,unit=km*k;
 ctx.strokeStyle='#d7e5ec';ctx.beginPath();ctx.moveTo(25,height-125);ctx.lineTo(25+unit,height-125);ctx.stroke();ctx.fillStyle='#d7e5ec';ctx.fillText((km<1?km*1000+' m':km+' km')+' (at center)',25,height-132);
}
function list(){
 const items=visible().sort((a,b)=>currentAge(a)-currentAge(b));$('target-total').textContent=items.length;$('targets').replaceChildren();
 if(!items.length){const p=document.createElement('p');p.className='empty';p.textContent='No positions match the selected filters.';$('targets').append(p);}
 for(const t of items){const b=document.createElement('button');b.className='target '+t.kind+(stale(t)?' old':'');const icon=document.createElement('span');icon.textContent=kinds[t.kind].icon;const label=document.createElement('span');label.className='identity';const name=document.createElement('b');name.textContent=t.name||t.ident;const sub=document.createElement('small');sub.textContent=t.ident+' · '+fmt(t.speed,' kn');label.append(name,sub);const age=document.createElement('span');age.className='age';age.textContent=ageText(currentAge(t));b.append(icon,label,age);b.onclick=()=>{selected=t.id;draw();detail();};$('targets').append(b);}
}
function detail(){const t=(state?.tracks||[]).find(x=>x.id===selected);$('selection').hidden=!t;if(!t)return;const root=$('selection');root.replaceChildren();const title=document.createElement('h3');title.textContent=t.name||t.ident;const source=document.createElement('small');source.textContent=t.source;const dl=document.createElement('dl');for(const [key,val] of [['Identity',t.ident],['Position age',ageText(currentAge(t))],['Status',stale(t)?'STALE POSITION':'Recent'],['Speed',fmt(t.speed,' kn')],['Altitude',fmt(t.altitude,' ft')],['Course',fmt(t.course,'°')],['Latitude',t.lat.toFixed(5)],['Longitude',t.lon.toFixed(5)]]){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key;dd.textContent=val;dl.append(dt,dd);}root.append(title,source,dl);}
const modeNames={adsb:'ADS-B',ais:'AIS',stopped:'STOPPED',stop:'STOPPED',switching:'SWITCHING',demo:'DEMO',error:'ERROR',acars:'ACARS',vdl2:'VDL2',hfdl:'HFDL',sonde:'RS41',wifi:'REMOTE ID'};
const compactNames={adsb:'ADS-B',ais:'AIS',acars:'ACARS',vdl2:'VDL2',hfdl:'HFDL',sonde:'RS41',wifi:'RID'};
function renderCycle(){const bar=$('cycle-bar'),saved=state.cycle||[],slots=[],seen=new Set();for(const slot of saved){if(!seen.has(slot.mode)){seen.add(slot.mode);slots.push(slot);}}if(state.config.wifi_enabled&&!seen.has('wifi'))slots.push({mode:'wifi',seconds:null});bar.replaceChildren();for(const slot of slots){const segment=document.createElement('i'),active=state.mode===slot.mode||(slot.mode==='wifi'&&state.wifi_active);segment.className='cycle-'+slot.mode+(active?' active':'');segment.title=modeNames[slot.mode]+(slot.seconds?' · '+slot.seconds+' s':' · parallel');segment.textContent=compactNames[slot.mode];bar.append(segment);}$('allocation').textContent=slots.length?slots.map(x=>compactNames[x.mode]).join(' · '):'No scanning modes selected';}
function render(){if(!state)return;$('mode').textContent=modeNames[state.mode]||state.mode;$('station-title').textContent=state.config.station_name;$('map-region-title').textContent=state.config.station_name;const primary=state.config.receiver_type==='hackrf'?'HackRF One':state.config.receiver_type==='wifi'?'No SDR':'RTL-SDR';$('receiver-name').textContent=primary+(state.config.wifi_enabled?' + Wi-Fi Remote ID':'');$('driver-setup').textContent=state.config.receiver_type==='wifi'?'Install Wi-Fi driver':'Install WinUSB';document.body.classList.toggle('user-background',state.has_background);if(state.has_background)document.body.style.setProperty('--user-background','url("/user-background?v=1")');$('demo-banner').hidden=state.policy!=='demo';const errorText=UpdateLogic.errorText(state.error,clientError);$('error').hidden=!errorText;$('error').textContent=errorText;$('status').textContent=state.mode==='error'?state.error:state.policy==='demo'?'Synthetic targets. The receiver is inactive.':state.mode==='adsb'?'Listening for aircraft · 1090 MHz':state.mode==='ais'?'Listening for vessels · 161.975 / 162.025 MHz':state.mode==='wifi'?'Listening for Wi-Fi Remote ID in parallel':state.mode==='switching'?'The previous decoder is closing before the next one starts.':'Reception is stopped.';$('countdown').textContent=state.remaining==null?'':state.remaining+' s';renderCycle();
 $('air-count').textContent=state.tracks.filter(t=>t.kind==='aircraft').length;$('sea-count').textContent=state.tracks.filter(t=>t.kind==='vessel').length;
 if(!cfgLoaded){for(const [k,v] of Object.entries(state.config)){const el=$('settings').elements[k];if(!el)continue;if(el.type==='checkbox')el.checked=v;else el.value=v;}[view.lat,view.lon]=UpdateLogic.initialCenter(state.config,satellite);cfgLoaded=true;}
 $('events').replaceChildren();for(const e of state.events){const p=document.createElement('p');p.textContent=new Date(e.time*1000).toLocaleTimeString('en-US')+' · '+e.text;$('events').append(p);}renderExtras();list();draw();detail();}
async function post(url,obj){if(!state)throw Error('No connection.');const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-Radar-Token':state.token},body:JSON.stringify(obj)});const result=await r.json();if(!r.ok)throw Error(result.error);}
let protocolLoaded=false,messageVersion='';
function renderExtras(){
 $('sonde-count').textContent=state.tracks.filter(t=>t.kind==='sonde').length;
 $('drone-count').textContent=state.tracks.filter(t=>t.kind==='drone').length;
 $('remote-status').textContent=state.remote_status||'Inactive';
 $('map-download-status').textContent=state.map_download_status||'';
 $('scan-wifi').disabled=!state.wifi_available;$('wifi-scan-label').classList.toggle('unavailable',!state.wifi_available);const hardwareMissing=!state.wifi_available&&!!state.wifi_hardware;$('wifi-notice').hidden=!hardwareMissing;$('wifi-notice-title').textContent=hardwareMissing?'Wi-Fi adapter detected — driver required':'';$('wifi-scan-reason').textContent=hardwareMissing?state.wifi_reason:'';$('wifi-reason-plain').textContent=hardwareMissing?'':state.wifi_available?'Wi-Fi receiver available · Remote ID capture runs in parallel.':state.wifi_reason;
 $('device-status').textContent=state.device_status||'Not checked.';
 const labels={acars:'ACARS',vdl2:'VDL2',hfdl:'HFDL',sonde:'RS41'};
 if(labels[state.mode])$('status').textContent='Receiving '+labels[state.mode]+' · '+state.config.protocols[state.mode].frequencies.map(x=>(x/1e6).toFixed(3)).join(', ')+' MHz';
 if(state.remaining!=null&&state.counts[state.mode]===0){const duration=state.mode==='adsb'?state.config.adsb_seconds:state.mode==='ais'?state.config.ais_seconds:state.config.protocols[state.mode]?.seconds;if(duration&&state.remaining<duration-15)$('status').textContent+=' · No messages decoded in this slot yet; check the antenna, gain, and local activity.';}
 if(!protocolLoaded&&state.config.protocols){
  for(const [mode,cfg] of Object.entries(state.config.protocols)){
   const f=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=labels[mode];f.append(legend);
   $('scan-'+mode).checked=cfg.enabled;
   const seconds=document.createElement('input');seconds.type='number';seconds.min=5;seconds.max=60;seconds.id=mode+'-seconds';seconds.value=cfg.seconds;seconds.setAttribute('aria-label',labels[mode]+' seconds');f.append(seconds,document.createTextNode(' s'));
   const freq=document.createElement('input');freq.type='text';freq.id=mode+'-frequencies';freq.value=cfg.frequencies.map(x=>x/1e6).join(', ');freq.setAttribute('aria-label',labels[mode]+' frequencies in MHz');f.append(freq);$('protocol-fields').append(f);
   }$('scan-adsb').checked=state.config.scan.adsb;$('scan-ais').checked=state.config.scan.ais;$('scan-wifi').checked=state.config.wifi_enabled&&state.wifi_available;protocolLoaded=true;
 }
 $('protocol-counts').textContent=Object.entries(state.counts).map(([k,v])=>k.toUpperCase()+': '+v).join(' · ');
 const deps=$('dependencies');deps.replaceChildren();for(const d of state.dependencies||[]){const row=document.createElement('div');row.className='dependency '+(d.ok?'ok':'missing');const title=document.createElement('b');title.textContent=(d.ok?'✓ ':'⚠ ')+d.name;const help=document.createElement('small');help.textContent=d.ok?'Ready':d.help;row.append(title,help);deps.append(row);}
 const version=(state.messages?.[0]?.time||0)+':'+(state.messages?.length||0);
 if(version!==messageVersion){messageVersion=version;$('decoded-messages').replaceChildren();for(const m of state.messages||[]){const d=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent=new Date(m.time*1000).toLocaleTimeString('en-US')+' · '+m.protocol.toUpperCase()+' · '+(m.ident||'Message')+' · '+(m.frequency/1e6).toFixed(3)+' MHz';pre.textContent=m.text;d.append(summary,pre);$('decoded-messages').append(d);}}
}
$('wifi-check').onclick=async()=>{try{await post('/api/command',{action:'wifi_check'});}catch(e){$('remote-status').textContent=e.message;}};
$('alfa-driver').onclick=async()=>{try{await post('/api/command',{action:'alfa_driver_setup',model:$('settings').elements.wifi_model.value});$('remote-status').textContent='An administrator window opened for driver installation.';}catch(e){$('remote-status').textContent=e.message;}};
$('wifi-quick-install').onclick=async()=>{try{const model=state.wifi_hardware;if(!model)throw Error('No supported Alfa adapter was detected.');await post('/api/command',{action:'alfa_driver_setup',model});$('wifi-scan-reason').textContent='Driver installation requested. Approve the Windows prompt, then select Check receiver.';}catch(e){$('wifi-scan-reason').textContent=e.message;}};
for(const [id,action] of [['wsl-host-setup','wsl_host_setup'],['wsl-bind','wsl_bind'],['wsl-attach','wsl_attach'],['wsl-driver-setup','wsl_driver_setup'],['wsl-detach','wsl_detach']])$(id).onclick=async()=>{try{await post('/api/command',{action});$('remote-status').textContent='The step was requested. Follow the installer window or run the check after it completes.';}catch(e){$('remote-status').textContent=e.message;}};
function scanningPayload(){const protocols={};for(const mode of ['acars','vdl2','hfdl','sonde'])protocols[mode]={enabled:$('scan-'+mode).checked,seconds:Number($(mode+'-seconds').value),frequencies:$(mode+'-frequencies').value.split(',').map(x=>Math.round(Number(x.trim())*1e6))};return {protocols,scan:{adsb:$('scan-adsb').checked,ais:$('scan-ais').checked},wifi_enabled:$('scan-wifi').checked};}
async function saveScanning(showStatus=true){await post('/api/protocols',scanningPayload());if(showStatus)$('protocol-saved').textContent='Selections saved.';}
$('protocol-settings').onsubmit=async e=>{e.preventDefault();try{await saveScanning();}catch(error){$('protocol-saved').textContent=error.message;}};
$('auto').onclick=async()=>{clientError='';try{await saveScanning(false);await post('/api/command',{action:'auto'});}catch(e){showError(e.message);}};
for(const action of ['stop','demo'])$(action).onclick=async()=>{clientError='';try{await post('/api/command',{action});}catch(e){showError(e.message);}};
$('settings').onsubmit=async e=>{e.preventDefault();const f=e.target.elements,c=state.config;const cfg={station_name:f.station_name.value.trim(),wifi_model:f.wifi_model.value,wifi_backend:f.wifi_backend.value,wifi_adapter:f.wifi_adapter.value,wsl_busid:f.wsl_busid.value.trim(),latitude:Number(f.latitude.value),longitude:Number(f.longitude.value),map_latitude:Number(f.map_latitude.value),map_longitude:Number(f.map_longitude.value),adsb_seconds:Number(f.adsb_seconds.value),ais_seconds:Number(f.ais_seconds.value),device_index:Number(f.device_index.value),rtl_serial:f.rtl_serial.value.trim(),ppm:Number(f.ppm.value),receiver_type:f.receiver_type.value,hackrf_serial:f.hackrf_serial.value.trim(),hackrf_lna:Number(f.hackrf_lna.value),hackrf_vga:Number(f.hackrf_vga.value),hackrf_amp:f.hackrf_amp.checked,scan:c.scan};[cfg.map_latitude,cfg.map_longitude]=UpdateLogic.settingsCenter(c,cfg);f.map_latitude.value=cfg.map_latitude;f.map_longitude.value=cfg.map_longitude;try{await post('/api/config',cfg);view.lat=cfg.map_latitude;view.lon=cfg.map_longitude;$('saved').textContent='Settings saved.';}catch(e){$('saved').textContent=e.message;}};
$('background-upload').onclick=async()=>{const file=$('background-file').files[0];if(!file){$('background-status').textContent='Select an image.';return;}try{const r=await fetch('/api/background',{method:'POST',headers:{'Content-Type':file.type,'X-Radar-Token':state.token},body:file});const result=await r.json();if(!r.ok)throw Error(result.error);$('background-status').textContent='Image saved.';document.body.style.setProperty('--user-background',`url("/user-background?v=${Date.now()}")`);document.body.classList.add('user-background');}catch(e){$('background-status').textContent=e.message;}};
$('background-clear').onclick=async()=>{try{await post('/api/command',{action:'clear_background'});document.body.classList.remove('user-background');$('background-status').textContent='Image removed.';}catch(e){$('background-status').textContent=e.message;}};
$('map-download').onclick=async()=>{try{const f=$('settings').elements;const next={latitude:Number(f.latitude.value),longitude:Number(f.longitude.value),map_latitude:Number(f.map_latitude.value),map_longitude:Number(f.map_longitude.value)};const [lat,lon]=UpdateLogic.settingsCenter(state.config,next);f.map_latitude.value=lat;f.map_longitude.value=lon;await post('/api/map-download',{latitude:lat,longitude:lon,radius:200});$('map-download-status').textContent='Download started. Progress appears here.';}catch(e){$('map-download-status').textContent=e.message;}};
$('device-check').onclick=async()=>{try{await post('/api/command',{action:'device_check'});}catch(e){$('device-status').textContent=e.message;}};
$('driver-setup').onclick=async()=>{try{const wifi=$('settings').elements.receiver_type.value==='wifi';const model=state.wifi_hardware||$('settings').elements.wifi_model.value;await post('/api/command',wifi?{action:'alfa_driver_setup',model}:{action:'driver_setup'});}catch(e){$('device-status').textContent=e.message;}};
$('exit').onclick=async()=>{try{await post('/api/exit',{});$('disconnect').hidden=false;$('disconnect').textContent='The application has stopped. You can close this tab.';}catch(e){showError(e.message);}};
for(const id of ['air-filter','sea-filter','sonde-filter','drone-filter','search','trails'])$(id).oninput=()=>{list();draw();};
function zoom(f){view.scale=Math.max(.65,Math.min(180,view.scale*f));draw();}
$('zoom-in').onclick=()=>zoom(1.4);$('zoom-out').onclick=()=>zoom(1/1.4);$('home').onclick=()=>{const [lat,lon]=UpdateLogic.initialCenter(state?.config||{latitude:0,longitude:0,map_latitude:0,map_longitude:0},satellite);view={lat,lon,scale:1};draw();};
canvas.onwheel=e=>{e.preventDefault();zoom(e.deltaY<0?1.15:1/1.15);};let drag=null;
canvas.onpointerdown=e=>{drag={x:e.clientX,y:e.clientY,lat:view.lat,lon:view.lon,moved:false};canvas.setPointerCapture(e.pointerId);};
canvas.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y,s=Math.min(width,height)/480*view.scale*40075.0167*Math.cos(drag.lat*Math.PI/180);drag.moved ||=Math.abs(dx)+Math.abs(dy)>4;view.lat=Math.max(mapBounds.south,Math.min(mapBounds.north,Math.atan(Math.sinh(Math.PI*(1-2*(mercY(drag.lat)-dy/s))))*180/Math.PI));view.lon=Math.max(mapBounds.west,Math.min(mapBounds.east,drag.lon-dx/s*360));draw();};
canvas.onpointerup=e=>{if(drag&&!drag.moved){const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;selected=hit.find(t=>Math.hypot(t.x-x,t.y-y)<22)?.id||null;detail();draw();}drag=null;};canvas.onpointercancel=()=>drag=null;
new ResizeObserver(draw).observe(canvas);
fetch('/places.json').then(r=>{if(!r.ok)throw Error('The place-name package is missing.');return r.json();}).then(data=>{places=data.places;draw();}).catch(e=>{showError(e.message);});
$('layer').onclick=()=>{satelliteOn=!satelliteOn;$('layer').textContent=satelliteOn?'Satellite':'Coastlines';draw();};
async function refreshMap(revision){
 if(mapRefreshPending)return;
 mapRefreshPending=true;
 try{
  const r=await fetch('/satellite.json',{cache:'no-store'});if(!r.ok)throw Error('Map metadata unavailable');
  const data=await r.json();const changed=mapRevision!==null&&mapRevision!==revision;
  satellite=data;tileCache.clear();mapRevision=revision;
  if(data.region)mapBounds={west:data.region[0],south:data.region[1],east:data.region[2],north:data.region[3]};
  if(state&&(changed||(view.lat===0&&view.lon===0))){[view.lat,view.lon]=changed&&data.center?data.center:UpdateLogic.initialCenter(state.config,data);}
  $('map-source').textContent='Sentinel-2 · '+(data.year||2024)+' · Stored offline';draw();
 }catch(e){$('map-source').textContent='Satellite package not found · Coastlines';}
 finally{mapRefreshPending=false;}
}
fetch('/land.json').then(r=>{if(!r.ok)throw Error('The offline map was not found.');return r.json();}).then(data=>{land=data.polygons;if(data.bounds&&!satellite)mapBounds={west:data.bounds[0],south:data.bounds[1],east:data.bounds[2],north:data.bounds[3]};draw();}).catch(e=>{showError(e.message);});
async function poll(){try{const r=await fetch('/api/state',{signal:AbortSignal.timeout(3000)});if(!r.ok)throw Error('server');state=await r.json();receivedAt=Date.now();$('disconnect').hidden=true;render();if(state.map_revision!==mapRevision)await refreshMap(state.map_revision);}catch(e){$('disconnect').hidden=false;draw();detail();}setTimeout(poll,1000);}poll();
setInterval(()=>{$('clock').textContent=new Date().toLocaleTimeString('en-US');},1000);
