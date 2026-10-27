import {RouteMap} from './map.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clone = value => JSON.parse(JSON.stringify(value));
const uid = () => crypto.randomUUID();
const fmt = s => {if(s===undefined||s===null)return '—';const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return `${String(h%24).padStart(2,'0')}:${String(m).padStart(2,'0')}${h>=24?' +'+Math.floor(h/24)+'d':''}`;};
const duration = s => {if(s===undefined||s===null)return '—';const m=Math.round(s/60);return m>=60?`${Math.floor(m/60)}h ${m%60}m`:`${m}m`;};
let data, stations, colors, map, config, scenario, evaluation=null;
let choices=[], choice=0, replaceIndex=-1, footIndex=-1, evalSerial=0, optionsSerial=0;
let undo=[],redo=[],messageTimer;
const CURRENT='t-run-map-current-v1', SAVED='t-run-map-saved-v1';
const emptyMarkup=$('itinerary-legs').innerHTML;
function canonicalLeg(leg){
  const keys=['id','mode','pattern','start','end','route','direction','headsign','shape_id','from','to','from_stop','to_stop','stations','geometry','geometry_source','distance'];
  return Object.fromEntries(keys.filter(k=>k in leg).map(k=>[k,leg[k]]));
}

function notify(text,kind='info'){
  clearTimeout(messageTimer);$('message').textContent=text;$('message').dataset.kind=kind;$('message').hidden=!text;
  if(kind!=='error')messageTimer=setTimeout(()=>$('message').hidden=true,9000);
}
function on(id,event,fn){$(id).addEventListener(event,e=>{Promise.resolve().then(()=>fn(e)).catch(error=>notify(error.message,'error'));});}
async function request(url,body){
  const response=await fetch(url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Request failed.');return result;
}
function name(id){return stations[id]?.name||id;}
function tabKey(value){try{if(value===null)sessionStorage.removeItem('t-run-google-key');else if(value!==undefined)sessionStorage.setItem('t-run-google-key',value);return sessionStorage.getItem('t-run-google-key')||'';}catch{return '';}}
function currentMode(){return document.querySelector('[name=mode]:checked').value;}
function assumptions(){return {run_pace:+$('run-pace').value,walk_pace:+$('walk-pace').value,buffer:+$('transfer-buffer').value,access:+$('access-time').value};}
function syncInputs(){
  $('scenario-name').value=scenario.name;$('service-date').value=scenario.date;$('start-time').value=scenario.time;
  const a=scenario.assumptions;$('run-pace').value=a.run_pace;$('walk-pace').value=a.walk_pace;$('transfer-buffer').value=a.buffer;$('access-time').value=a.access;
}
function serializable(value=scenario){
  const result=clone(value);
  result.legs=result.legs.map(l=>{
    if(l.geometry_source!=='google_routes')return l;
    return {...l,geometry:[stations[l.from].point,stations[l.to].point],geometry_source:'straight_line_sketch',
      note:'Session-only Google pedestrian geometry omitted. Re-request it or draw a foot path.'};
  });
  return result;
}
function autosave(){try{localStorage.setItem(CURRENT,JSON.stringify(serializable()));}catch{notify('Browser storage unavailable. Use Export JSON to save this scenario.','error');}}
function saved(){try{return JSON.parse(localStorage.getItem(SAVED)||'{}');}catch{return {};}}
function savedList(){const s=saved();$('saved-scenarios').innerHTML='<option value="">Choose a saved scenario…</option>'+Object.keys(s).map(k=>`<option value="${esc(k)}">${esc(s[k].name)}</option>`).join('');}
function mutate(fn){undo.push(clone(scenario));if(undo.length>50)undo.shift();redo=[];fn();evaluation=null;autosave();render();evaluate();}
async function evaluate(){
  const serial=++evalSerial;
  $('timing-note').textContent='Evaluating feasible trains and directed platform transfers…';
  try{const result=await request('/api/evaluate',scenario);if(serial!==evalSerial)return;evaluation=result;scenario.legs=result.legs.map(canonicalLeg);autosave();render();}
  catch(error){if(serial!==evalSerial)return;evaluation=null;render();$('timing-note').textContent=error.message;notify(error.message,'error');}
}
function setEndpoint(side,id){
  $(side+'-station').value=id||'';$(side+'-search').value=id?name(id):'';invalidateOptions();renderMap();
}
function resetEndpoints(){replaceIndex=-1;footIndex=-1;setEndpoint('from',scenario.legs.at(-1)?.to||'');setEndpoint('to','');render();}
function invalidateOptions(){optionsSerial++;choices=[];$('add-path').hidden=true;$('path-options').innerHTML='<p class="empty-copy">Preview a connection to see its path options.</p>';}
function pickStation(id){
  if(!$('from-station').value){setEndpoint('from',id);return;}
  if($('from-station').value===id){notify(`${name(id)} is your starting station. Choose another station as the destination.`);return;}
  setEndpoint('to',id);findPaths().catch(error=>notify(error.message,'error'));
}
async function findPaths(){
  const from=$('from-station').value,to=$('to-station').value;
  if(!from||!to||from===to)throw Error('Choose two different stations first.');
  const serial=++optionsSerial;
  choices=[];$('add-path').hidden=true;$('find-routes').disabled=true;$('find-routes').textContent='Finding connected paths…';
  try{
    if(currentMode()==='ride'){
      const result=await request('/api/options?'+new URLSearchParams({from,to,date:scenario.date,route:$('line-filter').value,time:scenario.time}));
      if(serial!==optionsSerial)return;choices=result.options;
      if(!choices.length){$('path-options').innerHTML=`<p class="notice">${esc(result.message)}</p>`;renderMap();return;}
    }else{
      choices=[{label:currentMode()==='run'?'Outdoor run':'Outdoor walk',transfers:0,legs:[{mode:currentMode(),from,to,
        geometry:[stations[from].point,stations[to].point],geometry_source:'straight_line_sketch',stations:[]}]}];
    }
    choice=0;renderOptions();renderMap();map.fit();
  }finally{$('find-routes').disabled=false;$('find-routes').textContent=currentMode()==='ride'?'Preview rail paths →':'Preview foot connection →';}
}
function chips(legs){return legs.map(l=>`<span class="chip" style="--route:${colors[l.route]||'#7952c7'}">${esc(l.route||l.mode.toUpperCase())}</span>`).join('<span aria-hidden="true">›</span>');}
function renderOptions(){
  $('path-options').innerHTML=choices.map((o,i)=>{
    const foot=o.legs[0].mode!=='ride';
    const intermediates=new Set(o.legs.flatMap(l=>l.stations));
    return `<button class="path-option" data-choice="${i}" aria-pressed="${i===choice}"><strong>${esc(o.label)}</strong><span class="path-chips">${chips(o.legs)}</span><small>${foot?'Foot sketch · editable waypoints · inspect street access':`${intermediates.size} stations · ${o.transfers} transfer${o.transfers===1?'':'s'}${o.revisited_stations?` · ${o.revisited_stations} repeated`:''}${o.estimated_transfers?' · estimated platform change':''} · follows official rail shapes`}</small>${o.transfers?`<small>Change at ${o.legs.slice(0,-1).map(l=>esc(name(l.to))).join(', ')}</small>`:''}</button>`;
  }).join('');
  $('add-path').hidden=!choices.length;$('add-path').textContent=replaceIndex>=0?'Replace this segment with selected path':'Add selected path to itinerary';
}
function addPath(){
  const selected=choices[choice];if(!selected)throw Error('Preview and choose a path first.');
  const previous=replaceIndex>=0?scenario.legs[replaceIndex-1]:scenario.legs.at(-1);
  if(previous&&previous.to!==selected.legs[0].from)throw Error(`This journey must continue from ${name(previous.to)}. Change From, or replace an earlier segment.`);
  mutate(()=>{
    const added=selected.legs.map(l=>({...clone(l),id:uid()}));
    if(replaceIndex>=0)scenario.legs.splice(replaceIndex,1,...added);else scenario.legs.push(...added);
  });
  const final=selected.legs.at(-1).to;replaceIndex=-1;footIndex=-1;setEndpoint('from',final);setEndpoint('to','');render();
  notify('Connection added. Choose the next destination to extend your route.');
}
function renderMap(){
  if(!map)return;
  map.setState({legs:scenario.legs,preview:choices[choice]?.legs||[],covered:new Set(evaluation?.covered||[]),
    from:$('from-station').value,to:$('to-station').value,edit:footIndex});
  $('map-instruction').textContent=footIndex>=0?'Edit foot path: click to add a waypoint; drag purple handles':!$('from-station').value?'Click a starting station':!$('to-station').value?`From ${name($('from-station').value)} → choose your next station`:'Preview a path, then add it to your itinerary';
}
function render(){
  $('undo').disabled=!undo.length;$('redo').disabled=!redo.length;
  $('editing-banner').hidden=replaceIndex<0;$('editing-banner').textContent=replaceIndex<0?'':`Replacing segment ${replaceIndex+1}. Reset to return to appending.`;
  const summary=evaluation?.summary;
  $('total-time').textContent=summary?duration(summary.elapsed):'—';
  $('mode-times').textContent=summary?`${duration(summary.ride)} / ${duration(summary.run+summary.walk)}`:'—';
  $('wait-times').textContent=summary?`${duration(summary.wait)} / ${duration(summary.transfer+summary.access)}`:'—';
  $('coverage-count').textContent=`${evaluation?.covered.length||0} / ${data.stations.length}`;
  if(evaluation){$('timing-note').textContent=evaluation.status!=='ok'?evaluation.message+(evaluation.summary.estimated?' Segments without a scheduled train use estimated typical ride times; totals are estimates.':''):scenario.legs.length?`Finish ${fmt(summary.finish)} · first-train → last-platform proxy ${duration(summary.record_proxy_seconds)}. Plan duration includes pre-start preparation. Scheduled estimates, not live predictions.`:'Choose a date and platform-ready service time. Schedules are estimates, not live predictions.';}
  $('itinerary-legs').innerHTML=scenario.legs.length?scenario.legs.map((leg,i)=>{
    const evaluated=evaluation?.legs[i],foot=leg.mode!=='ride',status=evaluated?.status||'pending';
    const item=evaluated||leg;
    const transfer=evaluated?.transfer_seconds?`<div class="transfer-note">↳ Internal transfer · ${duration(evaluated.transfer_seconds)} · directed platform ${esc(scenario.legs[i-1]?.to_stop||'')} → ${esc(leg.from_stop)} (includes buffer)</div>`:'';
    const ids=leg.stations||[];
    return `${transfer}<article class="leg-card" data-index="${i}" data-status="${status}"><div class="leg-header"><span class="leg-number">${String(i+1).padStart(2,'0')}</span><span class="chip" style="--route:${colors[leg.route]||'#7952c7'}">${esc(leg.route||leg.mode.toUpperCase())}</span><strong>${foot?'Foot connection':esc(item.headsign||'Rail ride')}</strong></div><div class="leg-body"><div class="leg-endpoints">${esc(name(leg.from))}<br><span class="muted">↓</span> ${esc(name(leg.to))}</div>
      <div class="leg-timing"><span>${status==='unavailable'?`~${fmt(evaluated.start_time)} → ${fmt(evaluated.estimated_arrival)} (estimated)`:`${fmt(evaluated?.departure)} → ${fmt(evaluated?.arrival)}`}</span><span>${duration(evaluated?.travel_seconds)} ${foot?leg.mode:'ride'}</span></div>
      <p class="leg-detail">${foot?`${((item.distance||0)/1000).toFixed(2)} km · ${esc(leg.geometry_source.replaceAll('_',' '))} · ${duration(evaluated?.access_seconds)} entry/exit`:`${ids.length} station calls · ${duration(evaluated?.wait_seconds)} wait${evaluated?.continuous?' · stay on the same train':''}`}</p>
      ${!foot?`<details><summary>Intermediate stops & train identity</summary><ol class="stop-list">${ids.map(s=>`<li>${esc(name(s))}</li>`).join('')}</ol><p class="leg-detail">${esc(item.trip_id||'Not yet evaluated')}<br>${esc(leg.from_stop)} → ${esc(leg.to_stop)}<br>Shape ${esc(leg.shape_id)} · direction ${esc(leg.direction)}</p></details>`:''}
      <div class="leg-actions"><button data-action="replace">Replace</button><button data-action="up" aria-label="Move segment ${i+1} up" ${i===0?'disabled':''}>↑</button><button data-action="down" aria-label="Move segment ${i+1} down" ${i===scenario.legs.length-1?'disabled':''}>↓</button>${foot?'<button data-action="edit-foot">Edit foot path</button>':''}<button data-action="remove">Delete</button></div>
      ${foot&&footIndex===i?`<div class="foot-editor"><p>Click the map to add waypoints. Endpoints stay at stations. Coordinates are latitude,longitude, one per line.</p><textarea aria-label="Foot path coordinates">${esc(leg.geometry.map(p=>p.join(',')).join('\n'))}</textarea><div><button data-action="apply-foot">Apply coordinates</button> <button data-action="suggest-foot">Suggest streets ↗</button> <button data-action="reset-foot">Reset sketch</button> <button data-action="done-foot">Done</button></div><p>Google street suggestions are session-only. Inspect entrances and crossings.</p></div>`:''}
      </div>${status==='blocked'||status==='unavailable'?`<div class="leg-error">${esc(item.message)}</div>`:''}</article>`;
  }).join(''):emptyMarkup;
  renderMap();
  if($('coverage-dialog').open)renderCoverage();
}
function renderCoverage(){
  const covered=new Set(evaluation?.covered||[]);
  $('coverage-list').innerHTML=[...data.stations].sort((a,b)=>Number(covered.has(a.id))-Number(covered.has(b.id))||a.name.localeCompare(b.name)).map(s=>`<button class="coverage-station" data-station="${esc(s.id)}" data-covered="${covered.has(s.id)}">${covered.has(s.id)?'✓':'○'} ${esc(s.name)} <small>${esc(s.routes.join(' / '))}</small></button>`).join('');
}
async function editAction(event){
  const button=event.target.closest('[data-action]');if(!button)return;
  const card=button.closest('[data-index]'),index=+card.dataset.index,leg=scenario.legs[index];
  switch(button.dataset.action){
    case 'remove':mutate(()=>scenario.legs.splice(index,1));footIndex=-1;invalidateOptions();render();break;
    case 'up':mutate(()=>[scenario.legs[index-1],scenario.legs[index]]=[scenario.legs[index],scenario.legs[index-1]]);footIndex=-1;render();break;
    case 'down':mutate(()=>[scenario.legs[index+1],scenario.legs[index]]=[scenario.legs[index],scenario.legs[index+1]]);footIndex=-1;render();break;
    case 'replace':replaceIndex=index;footIndex=-1;document.querySelector(`[name=mode][value="${leg.mode}"]`).checked=true;modeChanged();setEndpoint('from',leg.from);setEndpoint('to',leg.to);render();await findPaths();break;
    case 'edit-foot':footIndex=index;invalidateOptions();render();map.fit();break;
    case 'done-foot':footIndex=-1;render();break;
    case 'apply-foot':{
      const points=card.querySelector('textarea').value.trim().split('\n').map(line=>line.split(',').map(Number));
      updateFoot(index,points);break;
    }
    case 'reset-foot':updateFoot(index,[stations[leg.from].point,stations[leg.to].point],'straight_line_sketch');break;
    case 'suggest-foot':await map.suggestFoot(index);notify('Street suggestion loaded for this session. Check station entrances and pedestrian access.');break;
  }
}
function updateFoot(index,geometry,source){
  if(!scenario.legs[index]||scenario.legs[index].mode==='ride')return;
  if(geometry.length<2||geometry.some(p=>p.length!==2||p.some(n=>!Number.isFinite(n))))throw Error('Each point needs valid latitude,longitude coordinates.');
  mutate(()=>{scenario.legs[index].geometry=geometry;scenario.legs[index].geometry_source=source||(scenario.legs[index].geometry_source==='google_routes'?'google_routes':'user_drawn');});
}
function modeChanged(){
  $('route-field').hidden=currentMode()!=='ride';$('find-routes').textContent=currentMode()==='ride'?'Preview rail paths →':'Preview foot connection →';invalidateOptions();renderMap();
}
function download(blob,filename){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
function filename(extension){return (scenario.name.replace(/[^a-z0-9_-]+/gi,'-')||'t-run-route')+'.'+extension;}
function validateScenario(candidate){
  if(!candidate||candidate.schema!==1||candidate.dataset!==data.manifest.sha256||candidate.ruleset!==data.ruleset)throw Error('This scenario does not match the loaded schedule dataset/ruleset. Import a matching scenario or recreate its connections.');
  if(!Array.isArray(candidate.legs)||candidate.legs.length>250||!candidate.assumptions)throw Error('Invalid scenario format.');
}
async function loadScenario(candidate){
  validateScenario(candidate);const checked=await request('/api/evaluate',candidate);
  mutate(()=>{scenario={...clone(candidate),legs:checked.legs.map(canonicalLeg)};});syncInputs();resetEndpoints();map.fit();
}
async function demo(){
  notify('Building a track-following example with a rail transfer and outdoor run…');
  const red=await request('/api/options?'+new URLSearchParams({from:'place-alfcl',to:'place-pktrm',date:scenario.date,route:'Red'}));
  const green=await request('/api/options?'+new URLSearchParams({from:'place-pktrm',to:'place-kencl',date:scenario.date,route:'Green-B'}));
  if(!red.options.length||!green.options.length)throw Error('Example needs a published service date.');
  mutate(()=>{scenario.legs=[...red.options[0].legs,...green.options[0].legs,{mode:'run',from:'place-kencl',to:'place-fenwy',geometry:[stations['place-kencl'].point,stations['place-fenwy'].point],geometry_source:'straight_line_sketch',stations:[]}].map(l=>({...l,id:uid()}));});
  resetEndpoints();map.fit();notify('Example added: Alewife → Park Street → Kenmore → Fenway. Edit the run path to follow streets.');
}

async function boot(){
  [data,config]=await Promise.all([request('/api/network'),request('/api/config')]);
  stations=Object.fromEntries(data.stations.map(s=>[s.id,s]));colors=Object.fromEntries(data.routes.map(r=>[r.id,r.color]));
  const today=new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'});
  scenario={schema:1,id:uid(),name:'Boston rail rehearsal',dataset:data.manifest.sha256,ruleset:data.ruleset,
    date:data.dates.includes(today)?today:data.dates[0],time:'08:00',assumptions:assumptions(),legs:[]};
  try{const stored=JSON.parse(localStorage.getItem(CURRENT)||'null');if(stored){validateScenario(stored);scenario=stored;}}catch(error){notify('Saved draft could not be loaded: '+error.message,'error');}
  const stationList=[...data.stations].sort((a,b)=>a.name.localeCompare(b.name));
  ['from','to'].forEach(side=>{
    $(side+'-station').innerHTML='<option value="">Select station…</option>'+stationList.map(s=>`<option value="${esc(s.id)}">${esc(s.name)} · ${esc(s.routes.join('/'))}</option>`).join('');
    on(side+'-station','change',()=>{$(side+'-search').value=name($(side+'-station').value)||'';invalidateOptions();renderMap();});
    on(side+'-search','change',()=>{const text=$(side+'-search').value.toLowerCase().trim();const s=stationList.find(s=>s.name.toLowerCase()===text||s.id===text);if(s)setEndpoint(side,s.id);else if(!text)setEndpoint(side,'');});
  });
  $('station-options').innerHTML=stationList.map(s=>`<option value="${esc(s.name)}">${esc(s.routes.join('/'))}</option>`).join('');
  $('line-filter').insertAdjacentHTML('beforeend',data.routes.map(r=>`<option value="${esc(r.id)}">${esc(r.id)} only</option>`).join(''));
  $('map-legend').innerHTML=[['Red',colors.Red],['Orange',colors.Orange],['Blue',colors.Blue],['Green',colors['Green-B']],['Mattapan',colors.Mattapan],['Foot','#7952c7']].map(([r,c])=>`<span style="--route:${c}">${r}</span>`).join('');
  $('my-maps-link').href=config.my_maps_url;
  $('source-info').textContent=`Snapshot ${data.dates[0]}–${data.dates.at(-1)} · ${data.stations.length} rail stations · ${data.pattern_count} directed patterns · ${data.manifest.feed_info.feed_version}. All rail calls in this snapshot are scheduled non-timepoint estimates.`;
  syncInputs();savedList();
  map=new RouteMap($('map'),data,{pick:pickStation,drag:(a,b)=>{setEndpoint('from',a);setEndpoint('to',b);findPaths().catch(e=>notify(e.message,'error'));},foot:updateFoot,
    googleError:message=>{tabKey(null);$('map-status').innerHTML='<i></i> Geographic track preview';$('google-open').hidden=false;notify(message,'error');}});
  on('find-routes','click',findPaths);on('add-path','click',addPath);on('reset-endpoints','click',resetEndpoints);
  on('swap','click',()=>{const a=$('from-station').value,b=$('to-station').value;setEndpoint('from',b);setEndpoint('to',a);});
  on('line-filter','change',()=>{invalidateOptions();renderMap();});
  document.querySelectorAll('[name=mode]').forEach(input=>input.addEventListener('change',modeChanged));
  on('path-options','click',e=>{const b=e.target.closest('[data-choice]');if(b){choice=+b.dataset.choice;renderOptions();renderMap();}});
  on('itinerary-legs','click',async e=>{if(e.target.closest('#demo'))await demo();else await editAction(e);});
  on('scenario-name','change',()=>mutate(()=>scenario.name=$('scenario-name').value||'Untitled rehearsal'));
  on('service-date','change',()=>{mutate(()=>scenario.date=$('service-date').value);invalidateOptions();renderMap();});
  on('start-time','change',()=>mutate(()=>scenario.time=$('start-time').value));
  ['run-pace','walk-pace','transfer-buffer','access-time'].forEach(id=>on(id,'change',()=>mutate(()=>scenario.assumptions=assumptions())));
  on('undo','click',()=>{if(!undo.length)return;redo.push(clone(scenario));scenario=undo.pop();evaluation=null;syncInputs();autosave();resetEndpoints();evaluate();});
  on('redo','click',()=>{if(!redo.length)return;undo.push(clone(scenario));scenario=redo.pop();evaluation=null;syncInputs();autosave();resetEndpoints();evaluate();});
  on('clear','click',()=>{mutate(()=>scenario.legs=[]);resetEndpoints();});
  on('zoom-in','click',()=>map.zoom(1/1.3));on('zoom-out','click',()=>map.zoom(1.3));on('fit-map','click',()=>map.fit());
  ['help-open','google-open'].forEach(id=>on(id,'click',()=>$('help-dialog').showModal()));
  on('connect-google','click',async()=>{
    $('connect-google').disabled=true;$('google-feedback').textContent='Loading Google Maps…';
    try{const key=$('google-key').value.trim()||config.google_maps_key||tabKey();await map.connectGoogle(key);tabKey(key);$('google-feedback').textContent='Google Maps connected.';$('map-status').innerHTML='<i style="background:#248156"></i> Google Maps · MBTA tracks';$('google-open').hidden=true;$('help-dialog').close();}
    catch(error){$('google-feedback').textContent=error.message;throw error;}finally{$('connect-google').disabled=false;$('google-key').value='';}
  });
  on('coverage-open','click',()=>{renderCoverage();$('coverage-dialog').showModal();});
  on('coverage-list','click',e=>{const id=e.target.closest('[data-station]')?.dataset.station;if(id){$('coverage-dialog').close();pickStation(id);}});
  on('save','click',()=>{const s=saved();s[scenario.id]=serializable();localStorage.setItem(SAVED,JSON.stringify(s));savedList();$('saved-scenarios').value=scenario.id;notify(`Saved “${scenario.name}” in this browser.`);});
  on('duplicate','click',()=>{mutate(()=>{scenario.id=uid();scenario.name+=' · copy';});syncInputs();$('save').click();});
  on('load','click',async()=>{const s=saved()[$('saved-scenarios').value];if(!s)throw Error('Choose a saved scenario first.');await loadScenario(s);notify(`Loaded “${s.name}”.`);});
  on('import-json','click',()=>$('json-file').click());
  on('json-file','change',async e=>{const file=e.target.files[0];if(!file)return;if(file.size>4e6)throw Error('Scenario must be under 4 MB.');await loadScenario(JSON.parse(await file.text()));e.target.value='';notify('Scenario imported and recomputed.');});
  on('export-json','click',()=>download(new Blob([JSON.stringify(serializable(),null,2)],{type:'application/json'}),filename('json')));
  on('export-csv','click',()=>{
    if(!evaluation)throw Error('Wait for timetable evaluation first.');
    const rows=[['Order','Mode','Route','From station ID','From','To station ID','To','Status','Departure service time','Arrival service time','Wait seconds','Ride/foot seconds','Transfer seconds','Access seconds','Trip ID','From platform','To platform','Time kind','Dataset SHA256']];
    const serviceTime=s=>s===undefined?'':`${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor(s%3600/60)).padStart(2,'0')}:${String(Math.floor(s%60)).padStart(2,'0')}`;
    evaluation.legs.forEach((l,i)=>rows.push([i+1,l.mode,l.route||'',l.from,name(l.from),l.to,name(l.to),l.status,serviceTime(l.departure),serviceTime(l.arrival),l.wait_seconds??'',l.travel_seconds??'',l.transfer_seconds??'',l.access_seconds??'',l.trip_id||'',l.from_stop||'',l.to_stop||'',l.time_kind,data.manifest.sha256]));
    const csv=rows.map(row=>row.map(v=>'"'+String(v).replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"').join(',')).join('\r\n');
    download(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}),filename('csv'));
  });
  on('export-kml','click',async()=>{
    if(!scenario.legs.length)throw Error('Create an itinerary first, or download the full rail reference layer from Help.');
    const response=await fetch('/api/export/kml',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(scenario)});
    if(!response.ok)throw Error((await response.json()).error);
    download(await response.blob(),filename('kml'));notify('KML downloaded. In your Google My Maps project, choose Add layer → Import.');$('help-dialog').showModal();
  });
  resetEndpoints();render();await evaluate();
  const key=config.google_maps_key||tabKey();
  if(key){try{await map.connectGoogle(key);$('map-status').innerHTML='<i style="background:#248156"></i> Google Maps · MBTA tracks';$('google-open').hidden=true;}catch(error){tabKey(null);notify(error.message,'error');}}
}
boot().catch(error=>{notify('Could not start route studio: '+error.message,'error');$('map').textContent='Restart with: python3 -m frontend.map_editor.server';});
