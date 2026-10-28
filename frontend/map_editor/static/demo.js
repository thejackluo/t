/* Guided, self-running demo of the route studio. Everything drawn comes from the live API (official shapes, real
   timetable), so the times and paths shown are the ones the studio itself would produce. */
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const xy=p=>[(p[1]+71.1)*82000,(42.35-p[0])*111000];
const NS='http://www.w3.org/2000/svg';
const el=(tag,attrs={},text)=>{const n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!=null)n.textContent=text;return n;};
const fmt=s=>s==null?'—':`${String(Math.floor(s/3600)%24).padStart(2,'0')}:${String(Math.floor(s%3600/60)).padStart(2,'0')}`;
const dur=s=>s==null?'—':s>=3600?`${Math.floor(s/3600)}h ${Math.round(s%3600/60)}m`:`${Math.round(s/60)}m`;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const api=async(path,body)=>{const r=await fetch(path,body?{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}:undefined);const j=await r.json();if(!r.ok)throw Error(j.error||r.statusText);return j;};
const DATE=()=>{const d=new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'});return data.dates.includes(d)?d:data.dates[0];};

let data,stations,colors,names={},svg,view,target,playing=true,chapter=0,runToken=0,hoverSegments=[];
const layers={};

function boot(){
  svg=el('svg',{xmlns:NS});$('stage').append(svg);
  ['tracks','legs','flash','stations','labels'].forEach(k=>{layers[k]=el('g',{id:k});svg.append(layers[k]);});
  const pts=data.stations.map(s=>xy(s.point));
  const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);
  const full=[Math.min(...xs)-2000,Math.min(...ys)-1500,Math.max(...xs)-Math.min(...xs)+4000,Math.max(...ys)-Math.min(...ys)+3000];
  view=[...full];target=[...full];svg.setAttribute('viewBox',view.join(' '));
  data.lines.forEach(l=>layers.tracks.append(el('polyline',{points:l.geometry.map(xy).join(' '),fill:'none',stroke:colors[l.route]||'#888','stroke-width':2.2,opacity:.45,'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke'})));
  data.stations.forEach(s=>{const p=xy(s.point);layers.stations.append(el('circle',{cx:p[0],cy:p[1],r:s.routes.length>1?110:70,fill:s.kind==='silver'?'#7C878E':'#eaf2f1',stroke:'#0b141b','stroke-width':1.5,'vector-effect':'non-scaling-stroke','data-station':s.id}));});
  $('legend').innerHTML=[['Red',colors.Red],['Orange',colors.Orange],['Blue',colors.Blue],['Green',colors['Green-B']],['Silver Line',colors['741']],['Bus connector','#FFC72C','dash'],['Run / walk','#b48cff','dash'],['Backtracking','#ff5a4e','dash']].map(([n,c,d])=>`<span style="--c:${c}" ${d?'data-dash':''}>${n}</span>`).join('');
  controls();requestAnimationFrame(tick);
  window.FULL=full;
}
function tick(){
  const k=0.085;let moved=false;
  for(let i=0;i<4;i++){const d=target[i]-view[i];if(Math.abs(d)>0.5){view[i]+=d*k;moved=true;}}
  if(moved)svg.setAttribute('viewBox',view.join(' '));
  requestAnimationFrame(tick);
}
function flyTo(points,pad=1.35,minW=9000){
  const ps=points.map(xy);const xs=ps.map(p=>p[0]),ys=ps.map(p=>p[1]);
  let w=Math.max(minW,(Math.max(...xs)-Math.min(...xs))*pad),h=Math.max(minW*0.7,(Math.max(...ys)-Math.min(...ys))*pad);
  const aspect=svg.clientWidth/Math.max(1,svg.clientHeight);if(w/h<aspect)w=h*aspect;else h=w/aspect;
  const cx=(Math.max(...xs)+Math.min(...xs))/2,cy=(Math.max(...ys)+Math.min(...ys))/2;
  target=[cx-w/2,cy-h/2,w,h];
}
function controls(){
  let drag=null;
  svg.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,v:[...view]};svg.setPointerCapture(e.pointerId);});
  svg.addEventListener('pointermove',e=>{
    if(drag){const s=view[2]/svg.clientWidth;target=[drag.v[0]-(e.clientX-drag.x)*s,drag.v[1]-(e.clientY-drag.y)*s,view[2],view[3]];view=[...target];svg.setAttribute('viewBox',view.join(' '));return;}
    hover(e);
  });
  svg.addEventListener('pointerup',()=>{drag=null;});
  svg.addEventListener('wheel',e=>{e.preventDefault();const f=e.deltaY>0?1.18:1/1.18;const r=svg.getBoundingClientRect();const mx=view[0]+(e.clientX-r.left)/r.width*view[2],my=view[1]+(e.clientY-r.top)/r.height*view[3];target=[mx-(mx-view[0])*f,my-(my-view[1])*f,view[2]*f,view[3]*f];},{passive:false});
  $('fit').onclick=()=>{target=[...window.FULL];};
  $('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'⏸ Pause':'▶ Play';$('play').setAttribute('aria-pressed',playing);if(playing)run(chapter);};
  $('next').onclick=()=>run(Math.min(CHAPTERS.length-1,chapter+1));
  $('prev').onclick=()=>run(Math.max(0,chapter-1));
  $('dots').innerHTML=CHAPTERS.map((c,i)=>`<button data-i="${i}" title="${esc(c.title)}">${i+1}</button>`).join('');
  $('dots').onclick=e=>{const b=e.target.closest('button');if(b)run(+b.dataset.i);};
  $('track').onclick=e=>{const r=$('track').getBoundingClientRect();run(Math.min(CHAPTERS.length-1,Math.floor((e.clientX-r.left)/r.width*CHAPTERS.length)));};
}
function hover(e){
  const t=e.target.closest('[data-tip]');
  const tip=$('tip');
  if(!t){tip.style.opacity=0;return;}
  tip.innerHTML=t.dataset.tip;tip.style.opacity=1;tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px';
}
function caption(eyebrow,title,text,extra=''){
  const c=$('caption');c.hidden=true;
  setTimeout(()=>{$('cap-eyebrow').textContent=eyebrow;$('cap-title').textContent=title;$('cap-text').innerHTML=text;$('cap-extra').innerHTML=extra;c.hidden=false;},180);
}
function modes(on){document.querySelectorAll('#modes span').forEach(s=>{if(s.dataset.mode===on)s.setAttribute('data-on','');else s.removeAttribute('data-on');});}
function clear(){layers.legs.innerHTML='';layers.flash.innerHTML='';layers.labels.innerHTML='';}
function label(id){const s=stations[id];if(!s)return;const p=xy(s.point);layers.labels.append(el('text',{x:p[0]+140,y:p[1]-90,class:'station-label'},s.name));}
async function drawLeg(leg,evaluated,token,{color,dash,ms=1400}={}){
  /* The polyline draws itself along the official shape; segment hit areas carry the scheduled time for hover. */
  const pts=leg.geometry.map(xy);const stroke=color||(leg.mode==='ride'?colors[leg.route]:'#b48cff');
  const line=el('polyline',{points:pts.join(' '),fill:'none',stroke,'stroke-width':leg.mode==='ride'&&leg.kind!=='bus'?5:4.5,'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke','stroke-dasharray':dash||(leg.mode!=='ride'?'7 6':leg.kind==='bus'?'2 7':'none')});
  const halo=el('polyline',{points:pts.join(' '),fill:'none',stroke:'#0b141b','stroke-width':9,'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke',opacity:.8});
  layers.legs.append(halo,line);
  if(!dash&&leg.mode==='ride'||leg.mode!=='ride'){
    const len=line.getTotalLength();const d=dash||(leg.mode!=='ride'?'7 6':leg.kind==='bus'?'2 7':null);
    line.style.strokeDasharray=`${len} ${len}`;line.style.strokeDashoffset=len;line.getBoundingClientRect();
    line.style.transition=`stroke-dashoffset ${ms}ms ease-in-out`;line.style.strokeDashoffset=0;
    await sleep(ms);if(token!==runToken)return;
    line.style.transition='';line.style.strokeDasharray=d||'';line.style.strokeDashoffset='';
  }
  (evaluated?.segments||[]).forEach(s=>{
    const hit=el('polyline',{points:s.geometry.map(xy).join(' '),fill:'none',stroke:'#000',opacity:0,'stroke-width':16,'vector-effect':'non-scaling-stroke','data-tip':`<b>${esc(names[s.from])} → ${esc(names[s.to])}</b>${esc(leg.route_name||leg.route||leg.mode)} · ${s.time_kind==='estimated'?'~':''}${dur(s.seconds)}<br><small>${fmt(s.departure)} → ${fmt(s.arrival)} · scheduled estimate</small>`});
    layers.legs.append(hit);hoverSegments.push({hit,s});
  });
  if(evaluated&&leg.mode!=='ride')line.setAttribute('data-tip',`<b>${esc(names[leg.from])} → ${esc(names[leg.to])}</b>${leg.mode} ${dur(evaluated.travel_seconds)} · ${(leg.distance/1000).toFixed(2)} km<br><small>${evaluated.geometry_source==='google_routes'?'Google street route':'straight-line sketch'}</small>`);
  label(leg.from);label(leg.to);
}
async function pulseSegments(token,count=4){
  /* Show, don't tell: the hover tooltip pops along the ride by itself. */
  const picks=hoverSegments.filter((_,i)=>i%Math.max(1,Math.floor(hoverSegments.length/count))===0).slice(0,count);
  for(const {hit,s} of picks){
    if(token!==runToken)return;
    const p=xy(stations[s.to].point);const pt=svg.createSVGPoint();pt.x=p[0];pt.y=p[1];const sp=pt.matrixTransform(svg.getScreenCTM());
    const tip=$('tip');tip.innerHTML=hit.dataset.tip;tip.style.opacity=1;tip.style.left=(sp.x+14)+'px';tip.style.top=(sp.y+14)+'px';
    const ring=el('circle',{cx:p[0],cy:p[1],r:80,fill:'none',stroke:'#8fd3c7','stroke-width':3,'vector-effect':'non-scaling-stroke'});layers.flash.append(ring);
    await sleep(900);ring.remove();
  }
  $('tip').style.opacity=0;
}
async function evaluateLegs(legs,time='08:00'){return api('/api/evaluate',{date:DATE(),time,legs});}
async function path(from,to,opts={}){const q=new URLSearchParams({from,to,date:DATE(),time:opts.time||'08:00',route:opts.route||'',mode:opts.mode||'rail'});return api('/api/options?'+q);}

const CHAPTERS=[
 {title:'The network',async run(t){
   modes(null);clear();target=[...window.FULL];
   caption('01 · THE NETWORK',`${data.rail_station_count} rail stations + ${data.silver_station_count} Silver Line stops`,
     `Official MBTA GTFS shapes and the full timetable, pinned to one feed snapshot so every time is auditable. The goal: visit every station in one day — a Guinness-style all-stations run — and plan it to the minute.`,
     `<span class="stat"><b>${data.pattern_count}</b> stop patterns</span><span class="stat"><b>${data.bus.routes.length}</b> bus connector routes</span><span class="stat"><b>${data.dates.length}</b> service days</span>`);
   await sleep(5200);}},
 {title:'Ride: a path draws itself',async run(t){
   modes('ride');clear();
   const o=await path('place-alfcl','place-brntn',{route:'Red'});const legs=o.options[0].legs;const ev=await evaluateLegs(legs,'08:00');
   if(t!==runToken)return;
   flyTo(legs.flatMap(l=>l.geometry),1.25);
   caption('02 · RIDE MODE',`Alewife → Braintree on the Red Line`,`Click two stations — or drag along the track — and the path follows the official shape. The evaluator picks the real train: board ${fmt(ev.legs[0].departure)}, arrive ${fmt(ev.legs[0].arrival)}, ${ev.legs[0].stop_calls?.length||legs[0].stations.length} station calls.`,
     `<span class="stat"><b>${dur(ev.legs[0].travel_seconds)}</b> scheduled ride</span><span class="stat"><b>${dur(ev.legs[0].wait_seconds)}</b> wait</span><span class="stat">trip <b>${esc(ev.legs[0].trip_id)}</b></span>`);
   hoverSegments=[];await drawLeg(legs[0],ev.legs[0],t,{ms:2600});if(t!==runToken)return;
   await sleep(400);await pulseSegments(t,4);await sleep(1200);}},
 {title:'Transfers, platforms, street-level changes',async run(t){
   modes('ride');clear();
   const o=await path('place-lake','place-hsmnl',{time:'09:00'});const legs=o.options[0].legs;const ev=await evaluateLegs(legs,'09:00');
   if(t!==runToken)return;flyTo(legs.flatMap(l=>l.geometry),1.3);
   const tr=ev.legs.find(l=>l.transfer?.street_level);
   caption('03 · TRANSFERS',`Boston College → Heath Street`,`Multi-ride paths use GTFS directed transfers and pathways. Where the feed forbids an in-station change (Copley's reversal), the plan prices an <b>estimated street-level transfer</b> — exit, cross, re-enter — instead of refusing.`,
     `<span class="stat"><b>${legs.length-1}</b> transfer${legs.length===2?'':'s'}</span>${tr?`<span class="stat"><b>${dur(tr.transfer_seconds)}</b> ${esc(tr.transfer.via_names?.join(' → ')||'street-level')}</span>`:''}<span class="stat">finish <b>${fmt(ev.summary.finish)}</b></span>`);
   hoverSegments=[];for(const [i,l] of legs.entries()){await drawLeg(l,ev.legs[i],t,{ms:1500});if(t!==runToken)return;}
   await pulseSegments(t,3);await sleep(1200);}},
 {title:'Auto: rail vs run, fastest first',async run(t){
   modes('auto');clear();
   const rail=await path('place-fenwy','place-smary',{time:'09:30'}).catch(()=>({options:[]}));
   const run={mode:'run',from:'place-fenwy',to:'place-smary',geometry:[stations['place-fenwy'].point,stations['place-smary'].point],geometry_source:'straight_line_sketch'};
   let street=null;try{street=await api('/api/foot-route?'+new URLSearchParams({from:'place-fenwy',to:'place-smary'}));}catch{}
   const runLeg=street?{...run,geometry:street.geometry,geometry_source:'google_routes',provider_seconds:street.provider_seconds}:run;
   const evRun=await evaluateLegs([runLeg],'09:30');const evRail=rail.options[0]?await evaluateLegs(rail.options[0].legs,'09:30'):null;
   if(t!==runToken)return;
   flyTo([stations['place-fenwy'].point,stations['place-smary'].point,stations['place-kencl'].point],1.6,6000);
   const railMin=evRail?Math.round((evRail.summary.finish-evRail.legs[0].start_time)/60):null,runMin=Math.round(evRun.summary.elapsed/60);
   caption('04 · AUTO MODE',`Fenway → Saint Mary's Street: ${runMin} min on foot vs ${railMin??'—'} min by rail`,`Two Green branches, 270 m apart. Auto asks for the rail paths <i>and</i> a Google street run for the same pair, times each against your itinerary on the same clock, and puts the fastest first. Running is a first-class connector, never a hack.`,
     `<span class="stat"><b>${dur(evRun.legs[0].travel_seconds)}</b> run (${(evRun.legs[0].distance/1000).toFixed(2)} km${street?', street route':''})</span>${evRail?`<span class="stat"><b>${dur(evRail.summary.finish-evRail.legs[0].start_time)}</b> rail via ${esc(names[evRail.legs[0].to])}</span>`:''}`);
   hoverSegments=[];
   if(evRail){for(const [i,l] of rail.options[0].legs.entries()){await drawLeg(l,evRail.legs[i],t,{ms:900});if(t!==runToken)return;}}
   await drawLeg(runLeg,evRun.legs[0],t,{ms:1400});await sleep(2500);}},
 {title:'Bus connectors and the Silver Line',async run(t){
   modes('bus');clear();
   const bus=await path('place-forhl','place-asmnl',{mode:'bus',time:'10:30'});const evBus=bus.options[0]?await evaluateLegs(bus.options[0].legs,'10:30'):null;
   const sl=await path('place-sstat','place-chels',{route:'743',time:'10:30'});const evSl=sl.options[0]?await evaluateLegs(sl.options[0].legs,'10:30'):null;
   if(t!==runToken)return;
   const pts=[...(bus.options[0]?.legs[0].geometry||[]),...(sl.options[0]?.legs[0].geometry||[])];flyTo(pts,1.2);
   caption('05 · BUS & SILVER LINE',`Orange → Red by bus 21, and SL3 to Chelsea`,`Scheduled MBTA buses are legal connectors between lines (Forest Hills → Ashmont skips the whole downtown trunk) but <b>never count as station coverage</b>. The Silver Line is part of the record definition, so SL1–SL5 ride like any line with their own coverage count.`,
     `${evBus?`<span class="stat">bus 21 <b>${dur(evBus.legs[0].travel_seconds)}</b> + ${dur(evBus.legs[0].wait_seconds)} wait</span>`:''}${evSl?`<span class="stat">SL3 <b>${dur(evSl.legs[0].travel_seconds)}</b> · ${evSl.silver_covered.length} Silver stops</span>`:''}`);
   hoverSegments=[];
   if(evBus){await drawLeg(bus.options[0].legs[0],evBus.legs[0],t,{ms:1800});if(t!==runToken)return;}
   modes('silver');if(evSl){await drawLeg(sl.options[0].legs[0],evSl.legs[0],t,{ms:1800});}
   await pulseSegments(t,3);await sleep(1500);}},
 {title:'Backtracking: the speedrun check',async run(t){
   modes(null);clear();
   const a=await path('place-alfcl','place-pktrm',{route:'Red'}),b=await path('place-pktrm','place-mdftf',{route:'Green-E',time:'08:30'}),c=await path('place-mdftf','place-pktrm',{route:'Green-E',time:'09:00'}),d=await path('place-pktrm','place-alfcl',{route:'Red',time:'09:30'});
   const legs=[...a.options[0].legs,...b.options[0].legs,...c.options[0].legs,...d.options[0].legs];
   const ev=await evaluateLegs(legs,'08:00');const an=await api('/api/analyze',{date:DATE(),time:'08:00',legs,assumptions:{run_pace:6}});
   if(t!==runToken)return;flyTo(legs.flatMap(l=>l.geometry),1.2);
   hoverSegments=[];for(const [i,l] of legs.entries()){await drawLeg(l,ev.legs[i],t,{ms:700});if(t!==runToken)return;}
   const rep=new Set(an.repeated_pieces.map(p=>`${p.leg}:${p.segment}`));
   ev.legs.forEach((l,i)=>(l.segments||[]).forEach((s,k)=>{if(rep.has(`${i}:${k}`))layers.flash.append(el('polyline',{points:s.geometry.map(xy).join(' '),fill:'none',stroke:'#ff5a4e','stroke-width':3,'stroke-dasharray':'3 5','vector-effect':'non-scaling-stroke'}));}));
   const st=an.stretches[0],sc=st?.shortcuts[0],pr=sc?.proposal;
   caption('06 · BACKTRACKING',`${dur(an.backtrack_seconds)} of this plan re-rides track it already covered (${Math.round(an.backtrack_share*100)}%)`,`Any piece ridden twice is backtracking (dotted red). For each repeated stretch the planner prices real alternatives — bus, Silver, another rail path, or a run — from the moment you leave it, and shows the change as an approvable diff.`,
     sc?`<div class="diffcard"><div class="minus">− legs ${pr?pr.removed_legs.join(', '):st.legs.join(', ')}: ${esc(names[st.start])} → … → ${esc(names[st.end])} (${dur(st.elapsed_seconds)})</div><div class="plus">+ ${esc(sc.kind==='run'?sc.label:(sc.kind==='bus'?'Bus ':'')+sc.label)} ${esc(names[st.start])} → ${esc(names[sc.target])} · ${sc.time_kind==='estimated'?'~':''}${dur(sc.seconds)}</div>${pr?`<div>Finish ${fmt(pr.finish_before)} → <b>${fmt(pr.finish_after)}</b> · <b style="color:#8fd3c7">saves ${dur(sc.saves_seconds)}</b> · one click to approve</div>`:''}</div>`:'<span class="stat">no faster shortcut found for this stretch</span>');
   if(sc&&sc.kind==='run'){await sleep(1800);if(t!==runToken)return;await drawLeg({mode:'run',from:st.start,to:sc.target,geometry:[stations[st.start].point,stations[sc.target].point],distance:sc.meters},null,t,{color:'#8fd3c7',dash:'8 6',ms:1600});}
   await sleep(4500);}},
 {title:'Share it',async run(t){
   modes(null);target=[...window.FULL];
   caption('07 · SHARE & EXPORT',`One link, view-only, no account`,`The whole itinerary rides inside the URL (a few hundred characters), opens read-only with every time recomputed, and exports to Google My Maps as numbered KML legs. Open the studio to build your own.`,
     `<span class="stat"><a href="/" style="color:#8fd3c7">Open the route studio →</a></span>`);
   await sleep(6000);}}
];
async function run(i){
  chapter=i;runToken++;const t=runToken;
  document.querySelectorAll('#dots button').forEach((b,k)=>b.setAttribute('aria-pressed',k===i));
  $('progress').style.width=`${(i)/CHAPTERS.length*100}%`;
  try{await CHAPTERS[i].run(t);}catch(error){if(t===runToken)caption('DEMO','Live data unavailable',esc(error.message));}
  if(t!==runToken)return;
  $('progress').style.width=`${(i+1)/CHAPTERS.length*100}%`;
  if(playing)run((i+1)%CHAPTERS.length);
}
(async()=>{
  data=await api('/api/network');stations=Object.fromEntries(data.stations.map(s=>[s.id,s]));
  const all=[...data.routes,...(data.bus?.routes||[])];colors=Object.fromEntries(all.map(r=>[r.id,r.color]));names=Object.fromEntries(data.stations.map(s=>[s.id,s.name]));
  boot();run(0);
})();
