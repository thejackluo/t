import {RouteMap} from './map.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clone = value => JSON.parse(JSON.stringify(value));
const uid = () => crypto.randomUUID();
const fmt = s => {if(s===undefined||s===null)return '—';const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return `${String(h%24).padStart(2,'0')}:${String(m).padStart(2,'0')}${h>=24?' +'+Math.floor(h/24)+'d':''}`;};
const duration = s => {if(s===undefined||s===null)return '—';const m=Math.round(s/60);return m>=60?`${Math.floor(m/60)}h ${m%60}m`:`${m}m`;};
let data, stations, colors, routeNames={}, map, config, scenario, evaluation=null, analysis=null, analysisSerial=0;
let choices=[], choice=0, replaceIndex=-1, footIndex=-1, evalSerial=0, optionsSerial=0;
let undo=[],redo=[],messageTimer,lastAdded=[],viewer=false;
const CURRENT='t-run-map-current-v1', SAVED='t-run-map-saved-v1';
const emptyMarkup=$('itinerary-legs').innerHTML;
function canonicalLeg(leg){
  const keys=['id','mode','pattern','start','end','route','direction','headsign','shape_id','from','to','from_stop','to_stop','stations','geometry','geometry_source','distance','provider_seconds'];
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
const KEY='t-run-google-key';
function storedKey(value,remember){
  // null forgets everywhere; a value is kept on this device (localStorage) or for this tab only (sessionStorage).
  try{
    if(value===null){localStorage.removeItem(KEY);sessionStorage.removeItem(KEY);}
    else if(value!==undefined){(remember?localStorage:sessionStorage).setItem(KEY,value);(remember?sessionStorage:localStorage).removeItem(KEY);}
    return localStorage.getItem(KEY)||sessionStorage.getItem(KEY)||'';
  }catch{return '';}
}
const PREVIEW_LABEL={auto:'Preview fastest connection →',ride:'Preview rail paths →',bus:'Preview direct buses →',run:'Preview running route →'};
function currentMode(){return document.querySelector('[name=mode]:checked')?.value||'auto';}
function previewLabel(){return PREVIEW_LABEL[currentMode()]||PREVIEW_LABEL.auto;}
function assumptions(){return {run_pace:+$('run-pace').value,walk_pace:+$('walk-pace').value,buffer:+$('transfer-buffer').value,access:+$('access-time').value,station_change:+$('station-change').value};}
function syncInputs(){
  $('scenario-name').value=scenario.name;$('service-date').value=scenario.date;$('start-time').value=scenario.time;
  const a=scenario.assumptions;$('run-pace').value=a.run_pace;$('walk-pace').value=a.walk_pace;$('transfer-buffer').value=a.buffer;$('access-time').value=a.access;$('station-change').value=a.station_change??120;
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
function autosave(){if(viewer)return;try{localStorage.setItem(CURRENT,JSON.stringify(serializable()));}catch{notify('Browser storage unavailable. Use Export JSON to save this scenario.','error');}}
/* View-only share links carry the scenario in the URL fragment: no server storage, Google street geometry already
   replaced by serializable(), ride legs reduced to pattern/start/end because /api/evaluate rebuilds their shape. */
const SHARE='#share=';
function shareable(){
  const s=serializable();
  /* Keep links short enough to survive chat apps: no ids/notes, and only hand-drawn foot geometry travels (sketches are re-drawn from the stations). */
  s.legs=s.legs.map(l=>l.mode==='ride'?{mode:'ride',pattern:l.pattern,start:l.start,end:l.end}
    :l.geometry_source==='user_drawn'?{mode:l.mode,from:l.from,to:l.to,geometry:l.geometry.map(p=>[+p[0].toFixed(5),+p[1].toFixed(5)]),geometry_source:'user_drawn'}
    :{mode:l.mode,from:l.from,to:l.to});
  delete s.id;delete s.saved;
  return s;
}
const b64url={
  encode(bytes){let text='';for(let i=0;i<bytes.length;i+=0x8000)text+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(text).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');},
  decode(text){return Uint8Array.from(atob(text.replaceAll('-','+').replaceAll('_','/')),c=>c.charCodeAt(0));}
};
async function encodeShare(value){
  const bytes=new TextEncoder().encode(JSON.stringify(value));
  if(!('CompressionStream' in window))return 'j'+b64url.encode(bytes);
  const packed=await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate-raw'))).arrayBuffer();
  return 'z'+b64url.encode(new Uint8Array(packed));
}
async function decodeShare(raw){
  /* Chat apps and URL bars add or mangle characters around long fragments: keep only the link alphabet, and if the
     tail was damaged retry without the last few characters before giving up. */
  const text=decodeURIComponent(raw).replace(/[^A-Za-z0-9_\-]/g,'');
  if(text[0]!=='j'&&text[0]!=='z')throw Error('Unknown link format.');
  if(text[0]==='z'&&!('DecompressionStream' in window))throw Error('This browser cannot open compressed share links; use a current Chrome, Edge, Safari or Firefox.');
  let lastError;
  for(let trim=0;trim<=4;trim++){
    try{
      const bytes=b64url.decode(text.slice(1,text.length-trim));
      if(text[0]==='j')return JSON.parse(new TextDecoder().decode(bytes));
      return JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).text());
    }catch(error){lastError=error;}
  }
  throw Error(`${lastError.message}. The link was probably cut or altered when it was copied; ask for it again or use Import JSON.`);
}
function inflateShared(shared){
  /* Foot legs travel without sketch geometry; rebuild the straight-line sketch and ids the editor expects. */
  shared.legs=shared.legs.map(l=>({id:uid(),...l,...(l.mode!=='ride'&&!l.geometry?{geometry:[stations[l.from].point,stations[l.to].point],geometry_source:'straight_line_sketch'}:{})}));
  shared.id=shared.id||uid();
  return shared;
}
function enterViewer(on){
  viewer=on;document.body.classList.toggle('viewer',on);$('viewer-banner').hidden=!on;
  ['scenario-name','service-date','start-time'].forEach(id=>{$(id).disabled=on;});
}
function saved(){try{return JSON.parse(localStorage.getItem(SAVED)||'{}');}catch{return {};}}
function savedList(){const s=saved();$('saved-scenarios').innerHTML='<option value="">Choose a saved scenario…</option>'+Object.keys(s).map(k=>`<option value="${esc(k)}">${esc(s[k].name)}</option>`).join('');}
function mutate(fn){undo.push(clone(scenario));if(undo.length>50)undo.shift();redo=[];fn();evaluation=null;analysis=null;autosave();render();evaluate();}
async function evaluate(){
  const serial=++evalSerial;
  $('timing-note').textContent='Evaluating feasible trains and directed platform transfers…';
  try{const result=await request('/api/evaluate',scenario);if(serial!==evalSerial)return;evaluation=result;scenario.legs=result.legs.map(canonicalLeg);autosave();render();analyzeBacktracking();}
  catch(error){if(serial!==evalSerial)return;evaluation=null;render();$('timing-note').textContent=error.message;notify(error.message,'error');}
}
function setEndpoint(side,id){
  $(side+'-station').value=id||'';$(side+'-search').value=id?name(id):'';invalidateOptions();renderMap();
}
function resetEndpoints(){replaceIndex=-1;footIndex=-1;setEndpoint('from',scenario.legs.at(-1)?.to||'');setEndpoint('to','');render();}
function invalidateOptions(){optionsSerial++;choices=[];$('add-path').hidden=true;$('path-options').innerHTML='<p class="empty-copy">Preview a connection to see its path options.</p>';}
function pickStation(id){if(viewer)return;
  if(!$('from-station').value){setEndpoint('from',id);return;}
  if($('from-station').value===id){notify(`${name(id)} is your starting station. Choose another station as the destination.`);return;}
  setEndpoint('to',id);findPaths().catch(error=>notify(error.message,'error'));
}
async function findPaths(quiet=false){
  const from=$('from-station').value,to=$('to-station').value;
  if(!from||!to||from===to)throw Error('Choose two different stations first.');
  const serial=++optionsSerial,mode=currentMode();
  choices=[];$('add-path').hidden=true;$('find-routes').disabled=true;$('find-routes').textContent=mode==='auto'?'Comparing rail, bus and running…':mode==='ride'?'Finding connected paths…':mode==='bus'?'Finding direct buses…':'Finding the running route…';
  try{
    const optionsRequest=search=>request('/api/options?'+new URLSearchParams({from,to,date:scenario.date,route:search==='bus'?'':$('line-filter').value,time:scenario.time,mode:search}));
    const soft=search=>optionsRequest(search).catch(error=>({options:[],message:error.message}));
    const [rail,bus,run]=await Promise.all([
      mode==='run'||mode==='bus'?null:mode==='ride'?optionsRequest('rail'):soft('rail'),
      mode==='bus'?optionsRequest('bus'):mode==='auto'&&data.bus?.routes.length?soft('bus'):null,
      mode==='ride'||mode==='bus'?null:runOption(from,to,quiet)]);
    if(serial!==optionsSerial)return;
    const found=[...(rail?.options||[]).map(o=>({...o,kind:'ride'})),...(bus?.options||[]).map(o=>({...o,kind:'bus'})),...(run?[run]:[])];
    if(!found.length){$('path-options').innerHTML=`<p class="notice">${esc(rail?.message||bus?.message||'No connection found.')}</p>`;renderMap();return;}
    await timeChoices(found);
    if(serial!==optionsSerial)return;
    if(mode==='auto')found.sort((a,b)=>(a.arrival??Infinity)-(b.arrival??Infinity));
    choices=found;choice=0;renderOptions();
    if(rail&&!rail.options.length&&rail.message)$('path-options').insertAdjacentHTML('afterbegin',`<p class="notice">${esc(rail.message)}</p>`);
    renderMap();if(!quiet)map.fit();
  }finally{$('find-routes').disabled=false;$('find-routes').textContent=previewLabel();}
}
async function runOption(from,to,quiet){
  /* A running alternative for the same station pair. Dragging previews a straight-line sketch so Google is only asked once, on release. */
  const sketch={mode:'run',from,to,geometry:[stations[from].point,stations[to].point],geometry_source:'straight_line_sketch',stations:[]};
  const option={label:'Outdoor run',transfers:0,kind:'run',legs:[sketch]};
  if(quiet){option.note='Straight-line estimate while dragging; release to load the street route.';return option;}
  try{
    const route=await streetRoute(from,to);
    option.legs=[{...sketch,geometry:route.geometry,geometry_source:'google_routes',provider_seconds:route.provider_seconds}];
    option.provider_distance=route.provider_distance;option.provider_seconds=route.provider_seconds;
  }catch(error){option.note=`Straight-line estimate, not a street route: ${error.message}`;}
  return option;
}
async function streetRoute(from,to){
  if(config.foot_routing)return request('/api/foot-route?'+new URLSearchParams({from,to}));
  if(map?.googleMap)return map.footRoute(from,to);
  throw Error('street routing needs Google Maps connected in this browser or GOOGLE_ROUTES_API_KEY on the server.');
}
async function timeChoices(found){
  /* Predicted arrival of each alternative appended to (or replacing a segment of) the current itinerary, so rail and running compare on the same clock. */
  await Promise.all(found.map(async option=>{
    const candidate=clone(scenario);
    const previous=replaceIndex>=0?candidate.legs[replaceIndex-1]:candidate.legs.at(-1);
    const legs=option.legs.map(l=>({...clone(l),id:uid()}));
    if(previous&&previous.to===legs[0].from){if(replaceIndex>=0)candidate.legs.splice(replaceIndex,1,...legs);else candidate.legs.push(...legs);}
    else{candidate.legs=legs;option.standalone=!!previous;}
    try{
      const result=await request('/api/evaluate',candidate);
      const last=result.legs[result.legs.indexOf(result.legs.find(l=>l.id===legs.at(-1).id))]||result.legs.at(-1);
      option.arrival=last.status==='unavailable'?last.estimated_arrival:last.arrival;
      const mine=result.legs.filter(l=>legs.some(c=>c.id===l.id));
      option.estimated=mine.some(l=>l.status==='unavailable'||l.time_kind==='estimated')||option.kind==='run';
      option.estimated_transfer=mine.some(l=>l.transfer?.estimated);
      option.blocked=result.legs.some(l=>legs.some(c=>c.id===l.id)&&l.status==='blocked');
      option.minutes=Math.round(result.legs.filter(l=>legs.some(c=>c.id===l.id)).reduce((sum,l)=>sum+(l.travel_seconds||0)+(l.wait_seconds||0)+(l.transfer_seconds||0)+(l.access_seconds||0),0)/60);
    }catch(error){option.timing_error=error.message;}
  }));
}
function routeName(id){return routeNames[id]||id;}
function chips(legs){return legs.map(l=>`<span class="chip" style="--route:${colors[l.route]||'#7952c7'}">${esc(l.route?routeName(l.route):l.mode.toUpperCase())}</span>`).join('<span aria-hidden="true">›</span>');}
function renderOptions(){
  $('path-options').innerHTML=choices.map((o,i)=>{
    const foot=o.legs[0].mode!=='ride';
    const intermediates=new Set(o.legs.flatMap(l=>l.stations));
    const fastest=currentMode()==='auto'&&i===0&&choices.length>1&&o.arrival!==undefined&&!o.blocked;
    const kind=foot?'estimated run':o.kind==='bus'?(o.estimated?'estimated bus':'scheduled bus')+', estimated walk to the stop':o.estimated?'estimated rail':o.estimated_transfer?'scheduled rail, estimated transfer':'scheduled rail';
    const timing=o.blocked?'Does not connect from the current itinerary':o.arrival!==undefined?`Arrive ${fmt(o.arrival)} · ${o.minutes} min incl. waits${o.standalone?' (from service time, not chained)':''} · ${kind}`:o.timing_error?`Timing unavailable: ${esc(o.timing_error)}`:'';
    const footDetail=o.legs[0].geometry_source==='google_routes'?`${(o.provider_distance/1000).toFixed(2)} km Google street route · Google walking estimate ${duration(o.provider_seconds)} · session-only`:esc(o.note||'Straight-line sketch · editable waypoints');
    return `<button class="path-option" data-choice="${i}" aria-pressed="${i===choice}"><strong>${esc(o.label)}${fastest?'<span class="leg-badge" data-kind="scheduled">fastest</span>':''}</strong><span class="path-chips">${chips(o.legs)}</span>${timing?`<small class="option-timing">${timing}</small>`:''}<small>${foot?footDetail:`${intermediates.size} stations · ${o.transfers} transfer${o.transfers===1?'':'s'}${o.revisited_stations?` · ${o.revisited_stations} repeated`:''}${o.street_transfers?' · exit & re-enter at street level (estimated)':o.estimated_transfers?' · estimated platform change':''}${o.kind==='bus'?' · direct scheduled MBTA bus · connector only, earns no station coverage':' · follows official rail shapes'}`}</small>${o.transfers?`<small>Change at ${o.legs.slice(0,-1).map(l=>esc(name(l.to))).join(', ')}</small>`:''}</button>`;
  }).join('');
  $('add-path').hidden=!choices.length;$('add-path').textContent=replaceIndex>=0?'Replace this segment with selected path':'Add selected path to itinerary';
}
function addPath(){
  const selected=choices[choice];if(!selected)throw Error('Preview and choose a path first.');
  const previous=replaceIndex>=0?scenario.legs[replaceIndex-1]:scenario.legs.at(-1);
  if(previous&&previous.to!==selected.legs[0].from)throw Error(`This journey must continue from ${name(previous.to)}. Change From, or replace an earlier segment.`);
  mutate(()=>{
    const added=selected.legs.map(l=>({...clone(l),id:uid()}));lastAdded=added.map(l=>l.id);
    if(replaceIndex>=0)scenario.legs.splice(replaceIndex,1,...added);else scenario.legs.push(...added);
  });
  const final=selected.legs.at(-1).to;replaceIndex=-1;footIndex=-1;setEndpoint('from',final);setEndpoint('to','');render();
  const addedFoot=selected.legs[0].mode!=='ride'&&selected.legs[0].geometry_source!=='google_routes'?scenario.legs.findIndex(l=>l.id===lastAdded[0]):-1;
  if(addedFoot>=0)suggestStreets(addedFoot).catch(error=>notify(`Connection added as a straight-line sketch: ${error.message}`));
  else notify('Connection added. Choose the next destination to extend your route.');
}
async function suggestStreets(index){
  const leg=scenario.legs[index];if(!leg||leg.mode==='ride')return;
  let route;
  try{route=await streetRoute(leg.from,leg.to);}catch(error){throw Error(`${error.message} Use Edit foot path to draw it.`);}
  if(scenario.legs[index]?.id!==leg.id)return;
  mutate(()=>{Object.assign(scenario.legs[index],{geometry:route.geometry,geometry_source:'google_routes',provider_seconds:route.provider_seconds});});
  notify(`Street route loaded: ${(route.provider_distance/1000).toFixed(2)} km, Google walking estimate ${duration(route.provider_seconds)}. Session-only; inspect entrances.`);
}
async function streetRoutesForSketches(){
  /* Every run/walk leg that is only a straight-line sketch gets its Google street route (session-only), then the plan
     is re-timed once. Used when a shared link or saved scenario loads; failures leave the sketch and say so. */
  const sketches=scenario.legs.filter(l=>l.mode!=='ride'&&l.geometry_source==='straight_line_sketch');
  if(!sketches.length)return;
  let failed=0;
  await Promise.all(sketches.map(async leg=>{
    try{const route=await streetRoute(leg.from,leg.to);const live=scenario.legs.find(l=>l.id===leg.id);
      if(live)Object.assign(live,{geometry:route.geometry,geometry_source:'google_routes',provider_seconds:route.provider_seconds});}
    catch{failed++;}
  }));
  evaluation=null;render();evaluate();
  if(failed)notify(`${failed} running link${failed===1?'':'s'} stay straight-line sketches: street routing is unavailable here.`,'error');
}
const AUTO_ANALYZE_LEGS=8;
async function analyzeBacktracking(force=false){
  /* Speedrun check: which pieces are ridden twice, and what bus/Silver/rail/run shortcut would skip each repeated stretch.
     The shortcut search evaluates many alternatives, so long plans only run it on request to keep Auto previews fast. */
  const serial=++analysisSerial;
  if(scenario.legs.length<2){analysis=null;renderAnalysis();return;}
  if(!force&&scenario.legs.length>AUTO_ANALYZE_LEGS){analysis=null;renderAnalysis();return;}
  $('backtrack-run').disabled=true;$('backtrack-run').textContent='Checking…';
  try{const result=await request('/api/analyze',scenario);if(serial!==analysisSerial)return;analysis=result;}
  catch(error){if(serial!==analysisSerial)return;analysis=null;if(force)notify('Backtracking check failed: '+error.message,'error');}
  finally{if(serial===analysisSerial){$('backtrack-run').disabled=false;$('backtrack-run').textContent='Check backtracking →';}}
  renderAnalysis();renderMap();
}
function renderAnalysis(){
  const box=$('backtracking');
  if(scenario.legs.length<2||viewer&&!analysis){box.hidden=true;return;}
  box.hidden=false;$('backtrack-run').hidden=false;
  if(!analysis){$('backtrack-total').textContent='Not checked yet';$('backtrack-summary').textContent=`Plans longer than ${AUTO_ANALYZE_LEGS} legs are checked on request so previews stay fast.`;$('backtrack-list').innerHTML='';return;}
  const pct=Math.round(analysis.backtrack_share*100);
  $('backtrack-total').textContent=analysis.backtrack_seconds?`${duration(analysis.backtrack_seconds)} re-ridden · ${pct}% of moving time`:'No backtracking';
  $('backtrack-summary').textContent=analysis.backtrack_seconds?`${analysis.stretches.length} repeated stretch${analysis.stretches.length===1?'':'es'} · ${analysis.repeated_station_visits} repeated station visits${analysis.potential_saving_seconds?` · shortcuts below could save about ${duration(analysis.potential_saving_seconds)}`:' · no faster bus, Silver, rail or run shortcut found for these stretches'}. Any piece ridden again after it was already traversed counts; shortcut times use the timetable from the moment you leave the stretch start.`:'Every piece of this plan covers new ground.';
  const diff=(x,si,xi)=>{const p=x.proposal;if(!p)return '<small>Cannot be applied automatically (the reversed stretch ends mid-ride); use Preview and Replace.</small>';
    const label=l=>`${l.mode==='ride'?routeName(l.route):l.mode} ${name(l.from)} → ${name(l.to)}`;
    const removed=p.removed_legs.map(i=>scenario.legs[i-1]).filter(Boolean).map(label);
    const added=p.legs.filter(l=>!scenario.legs.some(o=>o.id&&o.id===l.id)).map(label);
    return `<div class="diff"><div class="diff-minus">− legs ${p.removed_legs.join(', ')}: ${esc(removed.join(' · '))}</div><div class="diff-plus">+ ${esc(added.join(' · '))}</div><div class="diff-result">Finish ${fmt(p.finish_before)} → <b>${fmt(p.finish_after)}</b>${p.status!=='ok'?` · <span class="diff-warn">later legs then report: ${esc(p.message)}</span>`:''}</div><button class="approve" data-stretch="${si}" data-shortcut="${xi}">Approve this change</button></div>`;};
  $('backtrack-list').innerHTML=analysis.stretches.map((s,si)=>`<article class="stretch"><strong>Leg${s.legs.length===1?'':'s'} ${s.legs.join(', ')}: ${esc(name(s.start))} → ${esc(name(s.end))}</strong><small>${s.stations.length-1} piece${s.stations.length===2?'':'s'} re-ridden · ${s.estimated?'~':''}${duration(s.elapsed_seconds)} from leaving ${esc(name(s.start))} to reaching ${esc(name(s.end))}${s.leaves!==undefined&&s.leaves!==null?` (${fmt(s.leaves)} → ${fmt(s.arrives)})`:''}</small>${s.shortcuts.length?`<div class="shortcuts">${s.shortcuts.map((x,xi)=>`<button class="shortcut" data-from="${esc(s.start)}" data-to="${esc(s.end)}" data-mode="${x.kind==='bus'?'bus':x.kind==='run'?'run':'ride'}" title="${esc(x.note||'')}"><b>Saves ${duration(x.saves_seconds)}</b> · ${esc(x.kind==='run'?x.label:(x.kind==='bus'?'Bus ':x.kind==='silver'?'Silver ':'')+x.label)} · ${x.time_kind==='estimated'?'~':''}${duration(x.seconds)}${x.via?.length?` via ${esc(x.via.join(', '))}`:''}${x.wait_seconds?`<small>incl. ${duration(x.wait_seconds)} wait</small>`:''}${x.then?`<small>then ride ${esc(name(x.then.from))} → ${esc(name(x.then.to))} in reverse (${duration(x.then.seconds)})</small>`:''}</button>${diff(x,si,xi)}`).join('')}</div>`:'<small>No faster shortcut found; try an earlier/later time or a different order.</small>'}</article>`).join('');
}
function renderMap(){
  if(!map)return;
  map.setState({legs:scenario.legs,preview:choices[choice]?.legs||[],covered:new Set(evaluation?.covered||[]),evaluated:evaluation?.legs||[],backtracked:new Set((analysis?.repeated_pieces||[]).map(p=>`${p.leg}:${p.segment}`)),
    from:$('from-station').value,to:$('to-station').value,edit:footIndex});
  $('map-instruction').textContent=footIndex>=0?'Edit foot path: click to add a waypoint; drag purple handles':!$('from-station').value?'Click a starting station':!$('to-station').value?`From ${name($('from-station').value)} → choose your next station`:'Preview a path, then add it to your itinerary';
}
function render(){
  $('undo').disabled=!undo.length;$('redo').disabled=!redo.length;
  $('editing-banner').hidden=replaceIndex<0;$('editing-banner').textContent=replaceIndex<0?'':`Replacing segment ${replaceIndex+1}. Reset to return to appending.`;
  const summary=evaluation?.summary;
  $('total-time').textContent=summary?duration(summary.elapsed):'—';
  $('mode-times').textContent=summary?`${summary.estimated_ride?'~':''}${duration(summary.ride+(summary.estimated_ride||0)-(summary.bus||0))} / ${duration(summary.run+summary.walk)} / ${duration(summary.bus||0)}`:'—';
  $('wait-times').textContent=summary?`${duration(summary.wait)} / ${duration(summary.transfer+summary.access)}`:'—';
  $('coverage-count').textContent=`${evaluation?.covered.length||0} / ${data.rail_station_count}`;
  $('coverage-note').textContent=`Silver Line ${evaluation?.silver_covered?.length||0} / ${data.silver_station_count} · visit rule pending Guinness clarification`;
  if(evaluation){$('timing-note').textContent=evaluation.status!=='ok'?evaluation.message+(evaluation.summary.estimated?' Segments without a scheduled train use estimated typical ride times; totals are estimates.':''):scenario.legs.length?`Finish ${fmt(summary.finish)} · first-train → last-platform proxy ${duration(summary.record_proxy_seconds)}. Plan duration includes pre-start preparation. Scheduled estimates, not live predictions.`:'Choose a date and platform-ready service time. Schedules are estimates, not live predictions.';}
  $('itinerary-legs').innerHTML=scenario.legs.length?scenario.legs.map((leg,i)=>{
    const evaluated=evaluation?.legs[i],foot=leg.mode!=='ride',status=evaluated?.status||'pending';
    const item=evaluated||leg;
    const badge=status==='unavailable'?'<span class="leg-badge">estimated</span>':evaluated?.transfer?.street_level?'<span class="leg-badge">est. street transfer</span>':evaluated?.transfer?.fallback?'<span class="leg-badge">est. platform change</span>':'';
    const stopTimes=!foot&&evaluated?.segments?.length?`<ol class="leg-stop-times">${evaluated.segments.map((s,k)=>`<li><span>${k===0?esc(name(s.from))+' → ':''}${esc(name(s.to))}</span><span>${s.time_kind==='estimated'?'~':''}${duration(s.seconds)}${s.arrival!==undefined?` · arr ${fmt(s.arrival)}`:''}</span></li>`).join('')}</ol>`:'';
    const street=evaluated?.transfer?.street_level?evaluated.transfer:null;
    const transfer=street?`<div class="transfer-note">↳ Street-level transfer (estimated) · ${duration(evaluated.transfer_seconds)} · GTFS forbids the in-station change ${esc(scenario.legs[i-1]?.to_stop||'')} → ${esc(leg.from_stop)}, so: exit ${esc(street.via_names?.[0]||street.via[0])}, about ${street.outdoor_meters} m outdoors, re-enter ${esc(street.via_names?.[1]||street.via[1])} (includes buffer)</div>`
      :evaluated?.transfer_seconds?`<div class="transfer-note">↳ Internal transfer · ${duration(evaluated.transfer_seconds)} · directed platform ${esc(scenario.legs[i-1]?.to_stop||'')} → ${esc(leg.from_stop)} (includes buffer)</div>`:'';
    const ids=leg.stations||[];
    return `${transfer}<article class="leg-card" data-index="${i}" data-status="${status}"><div class="leg-header"><span class="leg-number">${String(i+1).padStart(2,'0')}</span><span class="chip" style="--route:${colors[leg.route]||'#7952c7'}">${esc(leg.route?routeName(leg.route):leg.mode.toUpperCase())}</span><strong>${foot?'Foot connection':esc(item.headsign||(leg.kind==='bus'?'Bus ride':leg.kind==='silver'?'Silver Line ride':'Rail ride'))}${leg.kind==='bus'?' <small class="muted">bus connector · no coverage</small>':''}${badge}</strong></div><div class="leg-body"><div class="leg-endpoints">${esc(name(leg.from))}<br><span class="muted">↓</span> ${esc(name(leg.to))}</div>
      <div class="leg-timing"><span>${status==='unavailable'?`~${fmt(evaluated.start_time)} → ${fmt(evaluated.estimated_arrival)} (estimated)`:`${fmt(evaluated?.departure)} → ${fmt(evaluated?.arrival)}`}</span><span>${duration(evaluated?.travel_seconds)} ${foot?leg.mode:'ride'}</span></div>
      <p class="leg-detail">${foot?`${((item.distance||0)/1000).toFixed(2)} km · ${esc(leg.geometry_source.replaceAll('_',' '))} · ${duration(evaluated?.access_seconds)} entry/exit${item.provider_seconds?` · Google walking estimate ${duration(item.provider_seconds)}`:''}${leg.geometry_source==='straight_line_sketch'?' · straight-line estimate, not a street route':''}`:`${ids.length} station calls · ${duration(evaluated?.wait_seconds)} wait${evaluated?.continuous?' · stay on the same train':''}`}</p>
      ${!foot?`<details><summary>Intermediate stops & train identity</summary>${stopTimes||`<ol class="stop-list">${ids.map(s=>`<li>${esc(name(s))}</li>`).join('')}</ol>`}<p class="leg-detail">${esc(item.trip_id||'Not yet evaluated')}<br>${esc(leg.from_stop)} → ${esc(leg.to_stop)}<br>Shape ${esc(leg.shape_id)} · direction ${esc(leg.direction)}</p></details>`:''}
      <div class="leg-actions"><button data-action="replace">Replace</button><button data-action="up" aria-label="Move segment ${i+1} up" ${i===0?'disabled':''}>↑</button><button data-action="down" aria-label="Move segment ${i+1} down" ${i===scenario.legs.length-1?'disabled':''}>↓</button>${foot?'<button data-action="edit-foot">Edit foot path</button>':''}<button data-action="remove">Delete</button></div>
      ${foot&&footIndex===i?`<div class="foot-editor"><p>Click the map to add waypoints. Endpoints stay at stations. Coordinates are latitude,longitude, one per line.</p><textarea aria-label="Foot path coordinates">${esc(leg.geometry.map(p=>p.join(',')).join('\n'))}</textarea><div><button data-action="apply-foot">Apply coordinates</button> <button data-action="suggest-foot">Suggest streets ↗</button> <button data-action="reset-foot">Reset sketch</button> <button data-action="done-foot">Done</button></div><p>Google street suggestions are session-only. Inspect entrances and crossings.</p></div>`:''}
      </div>${status==='blocked'||status==='unavailable'?`<div class="leg-error">${esc(item.message)}</div>`:''}</article>`;
  }).join(''):emptyMarkup;
  renderMap();
  if($('coverage-dialog').open)renderCoverage();
}
function renderCoverage(){
  const covered=new Set([...(evaluation?.covered||[]),...(evaluation?.silver_covered||[])]);
  $('coverage-list').innerHTML=[...data.stations].sort((a,b)=>Number(a.kind==='silver')-Number(b.kind==='silver')||Number(covered.has(a.id))-Number(covered.has(b.id))||a.name.localeCompare(b.name)).map(s=>`<button class="coverage-station" data-station="${esc(s.id)}" data-covered="${covered.has(s.id)}">${covered.has(s.id)?'✓':'○'} ${esc(s.name)} <small>${esc(s.routes.map(routeName).join(' / '))}${s.kind==='silver'?' · Silver Line':''}</small></button>`).join('');
}
async function editAction(event){
  const button=event.target.closest('[data-action]');if(!button)return;
  const card=button.closest('[data-index]'),index=+card.dataset.index,leg=scenario.legs[index];
  switch(button.dataset.action){
    case 'remove':mutate(()=>scenario.legs.splice(index,1));footIndex=-1;invalidateOptions();render();break;
    case 'up':mutate(()=>[scenario.legs[index-1],scenario.legs[index]]=[scenario.legs[index],scenario.legs[index-1]]);footIndex=-1;render();break;
    case 'down':mutate(()=>[scenario.legs[index+1],scenario.legs[index]]=[scenario.legs[index],scenario.legs[index+1]]);footIndex=-1;render();break;
    case 'replace':replaceIndex=index;footIndex=-1;(document.querySelector(`[name=mode][value="${leg.mode}"]`)||document.querySelector('[name=mode][value="run"]')).checked=true;modeChanged();setEndpoint('from',leg.from);setEndpoint('to',leg.to);render();await findPaths();break;
    case 'edit-foot':footIndex=index;invalidateOptions();render();map.fit();break;
    case 'done-foot':footIndex=-1;render();break;
    case 'apply-foot':{
      const points=card.querySelector('textarea').value.trim().split('\n').map(line=>line.split(',').map(Number));
      updateFoot(index,points);break;
    }
    case 'reset-foot':updateFoot(index,[stations[leg.from].point,stations[leg.to].point],'straight_line_sketch');break;
    case 'suggest-foot':await suggestStreets(index);break;
  }
}
function updateFoot(index,geometry,source){
  if(!scenario.legs[index]||scenario.legs[index].mode==='ride')return;
  if(geometry.length<2||geometry.some(p=>p.length!==2||p.some(n=>!Number.isFinite(n))))throw Error('Each point needs valid latitude,longitude coordinates.');
  mutate(()=>{const l=scenario.legs[index];l.geometry=geometry;l.geometry_source=source||(l.geometry_source==='google_routes'?'google_routes':'user_drawn');if(l.geometry_source!=='google_routes')delete l.provider_seconds;});
}
function modeChanged(){
  $('route-field').hidden=currentMode()==='run';$('find-routes').textContent=previewLabel();invalidateOptions();renderMap();
}
function download(blob,filename){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
function filename(extension){return (scenario.name.replace(/[^a-z0-9_-]+/gi,'-')||'t-run-route')+'.'+extension;}
function validateScenario(candidate){
  if(!candidate||candidate.schema!==1||candidate.dataset!==data.manifest.sha256||candidate.ruleset!==data.ruleset)throw Error('This scenario does not match the loaded schedule dataset/ruleset. Import a matching scenario or recreate its connections.');
  if(!Array.isArray(candidate.legs)||candidate.legs.length>250||!candidate.assumptions)throw Error('Invalid scenario format.');
}
async function loadScenario(candidate){
  validateScenario(candidate);const checked=await request('/api/evaluate',candidate);
  mutate(()=>{scenario={...clone(candidate),legs:checked.legs.map(canonicalLeg)};});syncInputs();resetEndpoints();map.fit();streetRoutesForSketches();
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
  try{[data,config]=await Promise.all([request('/api/network'),request('/api/config')]);}
  catch(error){
    // Never a blank page: the data function may be cold-starting on a shared link; offer a retry.
    $('message').hidden=false;$('message').dataset.kind='error';$('message').innerHTML=`${esc('Could not load the schedule data: '+error.message)} <button class="text-button" onclick="location.reload()">Retry</button>`;
    throw error;
  }
  stations=Object.fromEntries(data.stations.map(s=>[s.id,s]));const allRoutes=[...data.routes,...(data.bus?.routes||[])];colors=Object.fromEntries(allRoutes.map(r=>[r.id,r.color]));routeNames=Object.fromEntries(allRoutes.map(r=>[r.id,r.name||r.id]));
  const today=new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'});
  scenario={schema:1,id:uid(),name:'Boston rail rehearsal',dataset:data.manifest.sha256,ruleset:data.ruleset,
    date:data.dates.includes(today)?today:data.dates[0],time:'08:00',assumptions:assumptions(),legs:[]};
  try{const stored=JSON.parse(localStorage.getItem(CURRENT)||'null');if(stored){validateScenario(stored);scenario=stored;}}catch(error){notify('Saved draft could not be loaded: '+error.message,'error');}
  if(location.hash.startsWith(SHARE)){
    try{
      const shared=inflateShared(await decodeShare(location.hash.slice(SHARE.length)));validateScenario(shared);
      const checked=await request('/api/evaluate',shared);
      scenario={...shared,legs:checked.legs.map(canonicalLeg)};enterViewer(true);
      streetRoutesForSketches();  // Links carry no Google geometry; fetch the street routes so runs are not straight lines.
    }catch(error){notify('Shared link could not be opened: '+error.message,'error');}
  }
  const stationList=[...data.stations].sort((a,b)=>a.name.localeCompare(b.name));
  ['from','to'].forEach(side=>{
    $(side+'-station').innerHTML='<option value="">Select station…</option>'+stationList.map(s=>`<option value="${esc(s.id)}">${esc(s.name)} · ${esc(s.routes.join('/'))}</option>`).join('');
    on(side+'-station','change',()=>{$(side+'-search').value=name($(side+'-station').value)||'';invalidateOptions();renderMap();});
    on(side+'-search','change',()=>{const text=$(side+'-search').value.toLowerCase().trim();const s=stationList.find(s=>s.name.toLowerCase()===text||s.id===text);if(s)setEndpoint(side,s.id);else if(!text)setEndpoint(side,'');});
  });
  $('station-options').innerHTML=stationList.map(s=>`<option value="${esc(s.name)}">${esc(s.routes.join('/'))}</option>`).join('');
  $('line-filter').insertAdjacentHTML('beforeend',data.routes.map(r=>`<option value="${esc(r.id)}">${esc(r.name||r.id)} only</option>`).join(''));
  $('map-legend').innerHTML=[['Red',colors.Red],['Orange',colors.Orange],['Blue',colors.Blue],['Green',colors['Green-B']],['Mattapan',colors.Mattapan],['Silver',colors['741']],['Bus','#FFC72C'],['Foot','#7952c7']].map(([r,c])=>`<span style="--route:${c}">${r}</span>`).join('');
  $('my-maps-link').href=config.my_maps_url;
  $('source-info').textContent=`Snapshot ${data.dates[0]}–${data.dates.at(-1)} · ${data.stations.length} rail stations · ${data.pattern_count} directed patterns · ${data.manifest.feed_info.feed_version}. All rail calls in this snapshot are scheduled non-timepoint estimates.`;
  syncInputs();savedList();
  let hoverTimer;
  // Live previews during a drag must not move the map under the pointer; only a completed drag re-fits.
  const preview=(a,b,quiet)=>{setEndpoint('from',a);setEndpoint('to',b);findPaths(quiet).catch(e=>notify(e.message,'error'));};
  map=new RouteMap($('map'),data,{pick:pickStation,drag:(a,b)=>{clearTimeout(hoverTimer);if(!viewer)preview(a,b,false);},foot:updateFoot,
    hover:(a,b)=>{clearTimeout(hoverTimer);if(viewer||!b||a===b)return;hoverTimer=setTimeout(()=>preview(a,b,true),180);},
    format:{name,fmt,duration,routeName},
    googleError:message=>{storedKey(null);$('map-status').innerHTML='<i></i> Geographic track preview';$('google-open').hidden=false;notify(message,'error');}});
  $('origin-hint').textContent=location.origin+'/*';
  on('find-routes','click',()=>findPaths());on('add-path','click',addPath);on('reset-endpoints','click',resetEndpoints);
  on('swap','click',()=>{const a=$('from-station').value,b=$('to-station').value;setEndpoint('from',b);setEndpoint('to',a);});
  on('line-filter','change',()=>{invalidateOptions();renderMap();});
  document.querySelectorAll('[name=mode]').forEach(input=>input.addEventListener('change',modeChanged));
  on('path-options','click',e=>{const b=e.target.closest('[data-choice]');if(b){choice=+b.dataset.choice;renderOptions();renderMap();}});
  on('itinerary-legs','click',async e=>{if(e.target.closest('#demo'))await demo();else await editAction(e);});
  on('scenario-name','change',()=>mutate(()=>scenario.name=$('scenario-name').value||'Untitled rehearsal'));
  on('service-date','change',()=>{mutate(()=>scenario.date=$('service-date').value);invalidateOptions();renderMap();});
  on('start-time','change',()=>mutate(()=>scenario.time=$('start-time').value));
  ['run-pace','walk-pace','transfer-buffer','access-time','station-change'].forEach(id=>on(id,'change',()=>mutate(()=>scenario.assumptions=assumptions())));
  on('undo','click',()=>{if(!undo.length)return;redo.push(clone(scenario));scenario=undo.pop();evaluation=null;syncInputs();autosave();resetEndpoints();evaluate();});
  on('redo','click',()=>{if(!redo.length)return;undo.push(clone(scenario));scenario=redo.pop();evaluation=null;syncInputs();autosave();resetEndpoints();evaluate();});
  on('clear','click',()=>{mutate(()=>scenario.legs=[]);resetEndpoints();});
  on('zoom-in','click',()=>map.zoom(1/1.3));on('zoom-out','click',()=>map.zoom(1.3));on('fit-map','click',()=>map.fit());
  ['help-open','google-open'].forEach(id=>on(id,'click',()=>$('help-dialog').showModal()));
  on('connect-google','click',async()=>{
    $('connect-google').disabled=true;$('google-feedback').textContent='Loading Google Maps…';
    try{const key=$('google-key').value.trim()||config.google_maps_key||storedKey();await map.connectGoogle(key);if(!config.google_maps_key)storedKey(key,$('remember-key').checked);$('google-feedback').textContent='Google Maps connected.';$('map-status').innerHTML='<i style="background:#248156"></i> Google Maps · MBTA tracks';$('google-open').hidden=true;$('help-dialog').close();}
    catch(error){$('google-feedback').textContent=error.message;throw error;}finally{$('connect-google').disabled=false;$('google-key').value='';}
  });
  on('forget-key','click',()=>{storedKey(null);$('google-feedback').textContent='Saved key removed from this browser. Reload to return to the track preview.';});
  on('coverage-open','click',()=>{renderCoverage();$('coverage-dialog').showModal();});
  on('backtrack-run','click',()=>analyzeBacktracking(true));
  on('backtrack-list','click',e=>{
    const ok=e.target.closest('.approve');
    if(ok){
      const p=analysis?.stretches[+ok.dataset.stretch]?.shortcuts[+ok.dataset.shortcut]?.proposal;if(!p)throw Error('This suggestion is no longer available; re-check backtracking.');
      mutate(()=>{scenario.legs=p.legs.map(l=>({...clone(l),id:l.id||uid()}));});analysis=null;renderAnalysis();notify(`Shortcut applied: legs ${p.removed_legs.join(', ')} replaced. Undo is available.`);return;
    }
    const b=e.target.closest('.shortcut');if(!b)return;const radio=document.querySelector(`[name=mode][value=${b.dataset.mode}]`);if(radio){radio.checked=true;$('find-routes').textContent=previewLabel();}replaceIndex=-1;footIndex=-1;setEndpoint('from',b.dataset.from);setEndpoint('to',b.dataset.to);return findPaths();});
  on('coverage-list','click',e=>{const id=e.target.closest('[data-station]')?.dataset.station;if(id){$('coverage-dialog').close();pickStation(id);}});
  on('share-link','click',async()=>{
    if(!scenario.legs.length)throw Error('Create an itinerary first.');
    const url=location.origin+location.pathname+SHARE+await encodeShare(shareable());
    const detail=`View-only link (${Math.round(url.length/1000)} k characters). Anyone opening it sees this itinerary and its times; running legs fetch their street routes on open.`;
    try{await navigator.clipboard.writeText(url);notify('Copied. '+detail);}
    catch{$('share-url').value=url;$('share-dialog').showModal();$('share-url').select();}
  });
  on('viewer-edit','click',()=>{
    enterViewer(false);history.replaceState(null,'',location.pathname);
    mutate(()=>{scenario.id=uid();scenario.name+=' · shared copy';});syncInputs();$('save').click();
    notify('Editable copy saved in this browser; the shared link itself is unchanged.');
  });
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
  const key=config.google_maps_key||storedKey();
  if(key){try{await map.connectGoogle(key);$('map-status').innerHTML='<i style="background:#248156"></i> Google Maps · MBTA tracks';$('google-open').hidden=true;}catch(error){notify(error.message,'error');}}
  if(!viewer)streetRoutesForSketches();  // An autosaved draft stores no Google geometry either; refetch the street routes once the studio is up.
}
boot().catch(error=>{notify('Could not start route studio: '+error.message,'error');$('map').textContent='Restart with: python3 -m frontend.map_editor.server';});
