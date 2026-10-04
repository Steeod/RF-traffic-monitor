const assert = require('node:assert/strict');
const logic = require('../app/web/update_logic.js');
const original={latitude:0,longitude:0,map_latitude:0,map_longitude:0};
const moved={...original,latitude:45.1,longitude:9.2};
assert.deepEqual(logic.settingsCenter(original,moved),[45.1,9.2]);
assert.deepEqual(logic.settingsCenter(original,{...moved,map_latitude:43,map_longitude:11}),[43,11]);
const custom={...moved,map_latitude:43,map_longitude:11};
assert.deepEqual(logic.settingsCenter(custom,{...custom,latitude:46}),[43,11]);
assert.deepEqual(logic.initialCenter(original,{region:[24.8,33.9,31,38.4]}),[36.15,27.9]);
assert.deepEqual(logic.initialCenter(moved,{center:[36,28]}),[45.1,9.2]);
assert.deepEqual(logic.initialCenter(custom,{center:[36,28]}),[43,11]);
assert.equal(logic.errorText('', 'Invalid frequencies'), 'Invalid frequencies');
assert.equal(logic.errorText('USB busy', ''), 'USB busy');
console.log('PASS: unset/followed/custom map centers and persistent client errors');
// Execute the real browser refresh routine with a completed replacement map.
const vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(require.resolve('../app/web/app.js'),'utf8');
const start=source.indexOf('async function refreshMap(');
const end=source.indexOf("fetch('/land.json')",start);
const label={textContent:''};let draws=0;
const context={UpdateLogic:logic,mapRefreshPending:false,mapRevision:1,
  satellite:null,tileCache:new Map([['old',{}]]),state:{config:custom},
  view:{lat:36,lon:28},mapBounds:{},$:()=>label,draw:()=>draws++,
  fetch:async()=>({ok:true,json:async()=>({year:2024,center:[45,9],region:[7,43,11,47],levels:{}})})};
vm.createContext(context);vm.runInContext(source.slice(start,end),context);
(async()=>{
  await context.refreshMap(2);
  assert.equal(context.mapRevision,2);assert.equal(context.tileCache.size,0);
  assert.equal(context.view.lat,45);assert.equal(context.view.lon,9);
  assert.equal(context.mapBounds.west,7);assert.equal(draws,1);
  context.fetch=async()=>{throw Error('temporary failure');};
  await context.refreshMap(3);
  assert.equal(context.mapRevision,2);assert.equal(context.mapRefreshPending,false);
  console.log('PASS: actual map refresh replaces cached tiles, recenters, and permits retry after failure');
})().catch(e=>{console.error(e);process.exitCode=1;});
