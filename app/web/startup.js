'use strict';
const technologyNames={adsb:'Aircraft · ADS-B',ais:'Vessels · AIS',acars:'ACARS',vdl2:'VDL2',hfdl:'HFDL',sonde:'Radiosonde · RS41',wifi:'Wi-Fi · Remote ID'};
let selectionBusy=false;
for(const [mode,label] of Object.entries(technologyNames)){
 const button=document.createElement('button');button.textContent=label;button.dataset.mode=mode;button.setAttribute('aria-pressed','false');
 button.onclick=async()=>{
  if(selectionBusy)return;
  selectionBusy=true;renderTechnologies();clientError='';
  try{
   const enabled=button.getAttribute('aria-pressed')!=='true';
   const request_id=crypto.randomUUID();
   await post('/api/scan-toggle',{mode,enabled,request_id});
   await waitForState(s=>s.last_scan_request===request_id);
   if(state.error)throw Error(state.error);
  }catch(error){showError(error.message);}finally{selectionBusy=false;renderTechnologies();}
 };$('technology-buttons').append(button);
}
function technologySelected(s,mode){return s.policy==='auto'&&(mode==='wifi'?s.config.wifi_enabled:mode in s.config.scan?s.config.scan[mode]:s.config.protocols[mode].enabled);}
function renderTechnologies(){
 for(const button of $('technology-buttons').children){const mode=button.dataset.mode;$('scan-'+mode).checked=technologySelected(state,mode);button.setAttribute('aria-pressed',String(technologySelected(state,mode)));button.disabled=selectionBusy||(mode==='wifi'?!state.wifi_available:state.config.receiver_type==='wifi');}
}
async function waitForState(predicate){
 const deadline=Date.now()+20000;
 while(Date.now()<deadline){const r=await fetch('/api/state',{signal:AbortSignal.timeout(3000)});if(!r.ok)throw Error('Cannot read application state.');const latest=await r.json();if(predicate(latest)){state=latest;receivedAt=Date.now();render();return;}await new Promise(resolve=>setTimeout(resolve,250));}
 throw Error('The application is still processing the request. Check the diagnostic history before retrying.');
}
const setupDialog=document.createElement('dialog');setupDialog.id='startup-dialog';setupDialog.setAttribute('aria-labelledby','startup-title');
setupDialog.innerHTML=`<form id="startup-form"><h2 id="startup-title">Set up your receiving station</h2><p>Choose your location and receiver. This location also centres the map and the demo.</p><label>Station name<input name="station_name" maxlength="50" required></label><label>Receiver<select name="receiver_type"><option value="rtl">RTL-SDR</option><option value="hackrf">HackRF One</option><option value="wifi">Wi-Fi Remote ID only</option></select></label><label>Country, city or island<input id="place-query" type="search" maxlength="160" autocomplete="off" placeholder="e.g. Rhodes, Greece or Milano, Italia"></label><button type="button" id="place-search">Search places</button><p class="muted">Online search via Photon / <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>. Choose a result to fill the coordinates, or enter them manually.</p><p id="place-status" role="status" aria-live="polite"></p><div id="place-results" aria-label="Place search results"></div><div class="form-grid"><label>Latitude<input name="latitude" type="number" min="-85" max="85" step="any" placeholder="e.g. 36.2" required></label><label>Longitude<input name="longitude" type="number" min="-180" max="180" step="any" placeholder="e.g. 27.95" required></label></div><button type="button" id="use-map-center">Use the current map centre</button><label>Map radius<select name="radius"><option value="50">50 km</option><option value="100">100 km</option><option value="200" selected>200 km</option></select></label><label><input name="download" type="checkbox" checked> Download this area's offline map now</label><p class="muted">The download needs internet and may take time and disk space. Uncheck to download later from Settings.</p><p id="startup-status" role="status"></p><div class="controls"><button class="primary" id="startup-save">Save and continue</button><button type="button" id="startup-cancel">Later</button></div></form>`;
document.body.append(setupDialog);
let placeTimer=null,placeRequest=null,placeRevision=0,selectedPlace=false;
function clearPlaceSearch(){
 clearTimeout(placeTimer);placeRequest?.abort();placeRevision++;selectedPlace=false;
 $('place-query').value='';$('place-results').replaceChildren();$('place-status').textContent='';
}
async function searchPlaces(){
 clearTimeout(placeTimer);placeRequest?.abort();const revision=++placeRevision;
 const query=$('place-query').value.trim();selectedPlace=false;$('place-results').replaceChildren();
 if(query.length<3){$('place-status').textContent=query?'Enter at least 3 characters.':'';return;}
 placeRequest=new AbortController();const controller=placeRequest;
 const timeout=setTimeout(()=>controller.abort(),15000);$('place-status').textContent='Searching…';
 try{
  const response=await fetch('/api/place-search',{method:'POST',headers:{'Content-Type':'application/json','X-Radar-Token':state.token},body:JSON.stringify({query}),signal:controller.signal});
  const data=await response.json();if(!response.ok)throw Error(data.error||'Place search failed.');
  if(revision!==placeRevision)return;
  $('place-status').textContent=data.results.length?'Choose the correct area:':'No places found. Try adding the country, or enter coordinates manually.';
  for(const place of data.results){
   const button=document.createElement('button');button.type='button';button.textContent=place.label;
   button.onclick=()=>{
    const f=$('startup-form').elements;f.latitude.value=place.latitude.toFixed(5);f.longitude.value=place.longitude.toFixed(5);
    selectedPlace=true;$('place-status').textContent='Selected: '+place.label+' · Coordinates filled. Save to centre the map.';
    for(const sibling of $('place-results').children)sibling.setAttribute('aria-pressed',String(sibling===button));
   };button.setAttribute('aria-pressed','false');$('place-results').append(button);
  }
 }catch(error){if(revision===placeRevision)$('place-status').textContent=error.name==='AbortError'?'Search timed out. Retry or clear the search and enter coordinates manually.':error.message;}
 finally{clearTimeout(timeout);}
}
$('place-search').onclick=searchPlaces;
$('place-query').oninput=()=>{
 clearTimeout(placeTimer);placeRequest?.abort();placeRevision++;selectedPlace=false;
 $('place-results').replaceChildren();$('place-status').textContent='';
 if($('place-query').value.trim().length>=3)placeTimer=setTimeout(searchPlaces,850);
};
$('place-query').onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();searchPlaces();}};
let setupPrompted=false;
function openStartup(){
 clearPlaceSearch();const f=$('startup-form').elements,c=state.config;f.station_name.value=c.station_name;f.receiver_type.value=c.receiver_type;
 f.latitude.value=c.setup_complete?c.latitude:'';f.longitude.value=c.setup_complete?c.longitude:'';
 $('startup-status').textContent=state.policy==='stopped'?'':'Stop reception before saving setup.';setupDialog.showModal();
}
function renderStartup(){if(!setupPrompted&&!state.config.setup_complete&&state.policy==='stopped'){setupPrompted=true;openStartup();}}
$('open-setup').onclick=openStartup;
$('startup-cancel').onclick=()=>setupDialog.close();
setupDialog.addEventListener('close',clearPlaceSearch);
$('use-map-center').onclick=()=>{clearPlaceSearch();const f=$('startup-form').elements;f.latitude.value=view.lat.toFixed(5);f.longitude.value=view.lon.toFixed(5);};
$('startup-form').onsubmit=async event=>{
 event.preventDefault();const f=event.target.elements,lat=Number(f.latitude.value),lon=Number(f.longitude.value);
 const cfg={...state.config,station_name:f.station_name.value.trim(),receiver_type:f.receiver_type.value,latitude:lat,longitude:lon,map_latitude:lat,map_longitude:lon,setup_complete:true};
 $('startup-save').disabled=true;
 try{
  if(state.policy!=='stopped')throw Error('Press Stop all before saving setup.');
  if($('place-query').value.trim()&&!selectedPlace)throw Error('Choose a place from the results, or clear the search to use manually entered coordinates.');
  await post('/api/config',cfg);
  await waitForState(s=>s.config.setup_complete&&s.config.latitude===lat&&s.config.longitude===lon&&s.config.receiver_type===cfg.receiver_type&&s.config.station_name===cfg.station_name);
  view={lat,lon,scale:1};cfgLoaded=false;render();
  if(f.download.checked){await post('/api/map-download',{latitude:lat,longitude:lon,radius:Number(f.radius.value)});$('map-download-status').textContent='Download requested. You can follow progress here.';}
  setupDialog.close();draw();
 }catch(error){$('startup-status').textContent=error.message;}finally{$('startup-save').disabled=false;}
};
