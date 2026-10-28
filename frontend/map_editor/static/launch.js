/* 30-second launch film of the route studio. Everything is fetched live from the same API the studio uses (official
   shapes, the pinned timetable, Google street routes); the script only decides what to show when. */
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const xy=p=>[(p[1]+71.1)*82000,(42.35-p[0])*111000];
const NS='http://www.w3.org/2000/svg';
const el=(tag,attrs={},text)=>{const n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!=null)n.textContent=text;return n;};
const fmt=s=>s==null?'—':`${String(Math.floor(s/3600)%24).padStart(2,'0')}:${String(Math.floor(s%3600/60)).padStart(2,'0')}`;
const dur=s=>s==null?'—':s>=3600?`${Math.floor(s/3600)}h ${Math.round(s%3600/60)}m`:`${Math.round(s/60)}m`;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const api=async(path,body)=>{const r=await fetch(path,body?{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}:undefined);const j=await r.json();if(!r.ok)throw Error(j.error||r.statusText);return j;};
const ease=t=>t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2;

let gmFailed=false,data,stations,colors,names={},svg,view,target,FULL,gmap=null,gpoly=null;
const layers={};
const DATE=()=>{const d=new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'});return data.dates.includes(d)?d:data.dates[0];};
const path=(from,to,o={})=>api('/api/options?'+new URLSearchParams({from,to,date:DATE(),time:o.time||'08:00',route:o.route||'',mode:o.mode||'rail'}));
const evaluate=(legs,time='08:00')=>api('/api/evaluate',{date:DATE(),time,legs});

/* ---- stage ---- */
function boot(){
  svg=el('svg',{xmlns:NS});$('stage').append(svg);
  ['tracks','legs','flash','stations','labels'].forEach(k=>{layers[k]=el('g',{id:k});svg.append(layers[k]);});
  const pts=data.stations.map(s=>xy(s.point)),xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);
  FULL=[Math.min(...xs)-2000,Math.min(...ys)-1500,Math.max(...xs)-Math.min(...xs)+4000,Math.max(...ys)-Math.min(...ys)+3000];
  fitAspect(FULL);view=[...FULL];target=[...FULL];svg.setAttribute('viewBox',view.join(' '));
  requestAnimationFrame(tick);
}
function fitAspect(b){const a=svg.clientWidth/Math.max(1,svg.clientHeight);if(b[2]/b[3]<a){const w=b[3]*a;b[0]-=(w-b[2])/2;b[2]=w;}else{const h=b[2]/a;b[1]-=(h-b[3])/2;b[3]=h;}return b;}
let speed=0.11;
function tick(){
  let moved=false;for(let i=0;i<4;i++){const d=target[i]-view[i];if(Math.abs(d)>0.5){view[i]+=d*speed;moved=true;}}
  if(moved){svg.setAttribute('viewBox',view.join(' '));const k=Math.min(1,Math.max(0.2,view[2]/FULL[2]));layers.stations.querySelectorAll('circle').forEach(c=>c.setAttribute('r',(+c.dataset.r)*k));layers.labels.querySelectorAll('text').forEach(t=>t.setAttribute('font-size',view[2]/72));}
  requestAnimationFrame(tick);
}
function flyTo(points,pad=1.3,minW=8000,s=0.11){
  speed=s;const ps=points.map(xy),xs=ps.map(p=>p[0]),ys=ps.map(p=>p[1]);
  const w=Math.max(minW,(Math.max(...xs)-Math.min(...xs))*pad),h=Math.max(minW*.6,(Math.max(...ys)-Math.min(...ys))*pad);
  const cx=(Math.max(...xs)+Math.min(...xs))/2,cy=(Math.max(...ys)+Math.min(...ys))/2;
  target=fitAspect([cx-w/2,cy-h/2,w,h]);
}
function clear(){layers.legs.innerHTML='';layers.flash.innerHTML='';layers.labels.innerHTML='';$('tip').style.opacity=0;}
function label(id){const s=stations[id];if(!s)return;const p=xy(s.point);layers.labels.append(el('text',{x:p[0]+view[2]/160,y:p[1]-view[2]/200,class:'station-label','font-size':view[2]/72},s.name));}
function screen(p){const q=xy(p),pt=svg.createSVGPoint();pt.x=q[0];pt.y=q[1];return pt.matrixTransform(svg.getScreenCTM());}

/* ---- overlays ---- */
function pill(id,html,color){const n=$(id);if(html==null){n.hidden=true;return;}if(id==='tag'){n.querySelector('span').textContent=html;n.querySelector('i').style.setProperty('--c',color||'#8fd3c7');}else n.innerHTML=html;n.hidden=false;}
const tag=(t,c)=>pill('tag',t,c),line=t=>pill('line',t),stats=arr=>pill('stats',arr?arr.map(s=>`<span>${s}</span>`).join(''):null);
function clock(sec){const c=$('clock');c.hidden=false;c.querySelector('span').textContent=fmt(sec);}
function count(n,total){const c=$('count');c.hidden=false;c.querySelector('b').textContent=n;c.querySelector('span').textContent=total;}
async function tip(stationPoint,html,ms=700){const sp=screen(stationPoint),t=$('tip');t.innerHTML=html;t.style.left=(sp.x+14)+'px';t.style.top=(sp.y+12)+'px';t.style.opacity=1;
  const q=xy(stationPoint),ring=el('circle',{cx:q[0],cy:q[1],r:90,fill:'none',stroke:'#8fd3c7','stroke-width':3,'vector-effect':'non-scaling-stroke'});layers.flash.append(ring);await sleep(ms);ring.remove();t.style.opacity=0;}

/* ---- drawing ---- */
async function reveal(line,ms){const len=line.getTotalLength();line.style.strokeDasharray=`${len} ${len}`;line.style.strokeDashoffset=len;line.getBoundingClientRect();line.style.transition=`stroke-dashoffset ${ms}ms cubic-bezier(.3,.7,.3,1)`;line.style.strokeDashoffset=0;await sleep(ms);line.style.transition='';}
async function drawTrack(l,ms){const line=el('polyline',{points:l.geometry.map(xy).join(' '),fill:'none',stroke:colors[l.route]||'#888','stroke-width':3,opacity:.9,'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke'});layers.tracks.append(line);await reveal(line,ms);line.style.strokeDasharray='';line.setAttribute('opacity',.42);}
function dot(s){const p=xy(s.point),r=s.routes.length>1?110:70,c=el('circle',{cx:p[0],cy:p[1],r:0,'data-r':r,fill:s.kind==='silver'?'#7C878E':'#eaf2f1',stroke:'#070d12','stroke-width':1.5,'vector-effect':'non-scaling-stroke'});layers.stations.append(c);c.style.transition='r .35s cubic-bezier(.2,1.4,.4,1)';requestAnimationFrame(()=>c.setAttribute('r',r*Math.min(1,view[2]/FULL[2])));}
async function drawLeg(leg,ms=900,{color,dash,width}={}){
  const pts=leg.geometry.map(xy),stroke=color||(leg.mode==='ride'?colors[leg.route]:'#b48cff');
  const d=dash||(leg.mode!=='ride'?'7 6':leg.kind==='bus'?'2 7':'');
  layers.legs.append(el('polyline',{points:pts.join(' '),fill:'none',stroke:'#070d12','stroke-width':(width||5)+4,'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke',opacity:.85}));
  const line=el('polyline',{points:pts.join(' '),fill:'none',stroke,'stroke-width':width||6,'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke'});layers.legs.append(line);
  await reveal(line,ms);line.style.strokeDasharray=d;
}

/* ---- Google map for the street scene ---- */
const NIGHT=[{elementType:'geometry',stylers:[{color:'#131c24'}]},{elementType:'labels.text.fill',stylers:[{color:'#8da0ab'}]},{elementType:'labels.text.stroke',stylers:[{color:'#0b141b'}]},{featureType:'poi',stylers:[{visibility:'off'}]},{featureType:'road',elementType:'geometry',stroke:1,stylers:[{color:'#2a3844'}]},{featureType:'road',elementType:'geometry.stroke',stylers:[{color:'#1a252e'}]},{featureType:'road.arterial',elementType:'geometry',stylers:[{color:'#38495a'}]},{featureType:'transit',elementType:'geometry',stylers:[{color:'#243241'}]},{featureType:'water',elementType:'geometry',stylers:[{color:'#0b141b'}]},{featureType:'landscape',stylers:[{color:'#121a21'}]}];
function loadGoogle(key){
  if(!key)return Promise.resolve(false);
  return new Promise(res=>{
    const t=setTimeout(()=>res(false),6000);
    window.gm_authFailure=()=>{clearTimeout(t);gmFailed=true;res(false);};
    window.initLaunchMap=()=>{clearTimeout(t);try{gmap=new google.maps.Map($('gmap'),{center:{lat:42.345,lng:-71.1},zoom:15,disableDefaultUI:true,styles:NIGHT,backgroundColor:'#070d12'});window.gmTiles=new Promise(r=>{google.maps.event.addListenerOnce(gmap,'tilesloaded',()=>r(true));setTimeout(()=>r(false),4000);});res(true);}catch{res(false);}};
    const s=document.createElement('script');s.src='https://maps.googleapis.com/maps/api/js?'+new URLSearchParams({key,callback:'initLaunchMap',loading:'async',v:'weekly'});s.onerror=()=>{clearTimeout(t);res(false);};document.head.append(s);
  });
}
async function googleRun(leg,ms=1600){
  const ll=leg.geometry.map(p=>({lat:p[0],lng:p[1]}));const b=new google.maps.LatLngBounds();ll.forEach(p=>b.extend(p));
  gmap.fitBounds(b,{top:120,bottom:90,left:80,right:80});
  [leg.from,leg.to].forEach(id=>new google.maps.Marker({position:{lat:stations[id].point[0],lng:stations[id].point[1]},map:gmap,label:{text:names[id],color:'#eaf2f1',fontWeight:'700',fontSize:'13px'},icon:{path:google.maps.SymbolPath.CIRCLE,scale:7,fillColor:'#eaf2f1',fillOpacity:1,strokeColor:'#070d12',strokeWeight:2}}));
  $('gmap').classList.add('on');await sleep(500);
  gpoly=new google.maps.Polyline({map:gmap,path:[],strokeColor:'#b48cff',strokeOpacity:1,strokeWeight:6});
  const halo=new google.maps.Polyline({map:gmap,path:[],strokeColor:'#070d12',strokeOpacity:.9,strokeWeight:10,zIndex:-1});
  const t0=performance.now();await new Promise(r=>{const step=()=>{const k=ease(Math.min(1,(performance.now()-t0)/ms)),n=Math.max(2,Math.round(ll.length*k));gpoly.setPath(ll.slice(0,n));halo.setPath(ll.slice(0,n));if(k<1)requestAnimationFrame(step);else r();};step();});
}

/* ---- the film ---- */
async function film(){
  const [cfg,ride,xfer,railFR,street,bus21,bus109,bus8,sl3,day]=await Promise.all([
    api('/api/config'),
    path('place-alfcl','place-brntn',{route:'Red'}),
    path('place-lake','place-hsmnl',{time:'09:00'}),
    path('place-fenwy','place-smary',{time:'09:30'}).catch(()=>({options:[]})),
    api('/api/foot-route?'+new URLSearchParams({from:'place-fenwy',to:'place-smary'})).catch(()=>null),
    path('place-forhl','place-asmnl',{mode:'bus',time:'10:30'}),path('place-harsq','place-sull',{mode:'bus',time:'10:30'}).catch(()=>({options:[]})),path('place-rugg','place-kencl',{mode:'bus',time:'10:30'}).catch(()=>({options:[]})),
    path('place-sstat','place-chels',{route:'743',time:'10:30'}),
    fullDay()
  ]);
  let gm=await loadGoogle(cfg.google_maps_key);if(gm){gm=await window.gmTiles&&!gmFailed;}  // a referrer-restricted or invalid key never renders tiles: fall back to the SVG street route
  const runLeg={mode:'run',from:'place-fenwy',to:'place-smary',geometry:street?street.geometry:[stations['place-fenwy'].point,stations['place-smary'].point],geometry_source:street?'google_routes':'straight_line_sketch',provider_seconds:street?.provider_seconds};
  const [evRide,evX,evRun,evRail,evBus,evSl,evDay]=await Promise.all([evaluate(ride.options[0].legs),evaluate(xfer.options[0].legs,'09:00'),evaluate([runLeg],'09:30'),railFR.options[0]?evaluate(railFR.options[0].legs,'09:30'):null,evaluate(bus21.options[0].legs,'10:30'),evaluate(sl3.options[0].legs,'10:30'),evaluate(day.legs)]);
  const analysis=api('/api/analyze',{date:DATE(),time:'08:00',legs:day.legs,assumptions:{run_pace:6}}).catch(()=>null);

  /* 0.0 – 2.2 s  title (the live data loads behind it) */
  const t0=performance.now();const at=ms=>sleep(Math.max(0,t0+ms-performance.now()));
  await at(1400);$('title').hidden=true;

  /* 2.2 – 8.0 s  the map draws itself, line by line, camera easing out from downtown */
  const dt=xy([42.3555,-71.06]);target=fitAspect([dt[0]-6000,dt[1]-4000,12000,8000]);view=[...target];svg.setAttribute('viewBox',view.join(' '));
  speed=0.035;target=fitAspect([...FULL]);
  const groups=[['Red',['Red','Mattapan'],'Red Line'],['Orange',['Orange'],'Orange Line'],['Blue',['Blue'],'Blue Line'],['Green-B',['Green-B','Green-C','Green-D','Green-E'],'Green Line · 4 branches'],['741',['741','742','743','746','749','751'],'Silver Line']];
  for(const [c,routes,name] of groups){
    tag(name,colors[c]);
    const ls=data.lines.filter(l=>routes.includes(l.route));
    ls.forEach(l=>drawTrack(l,650));
    await sleep(360);
    data.stations.filter(s=>s.routes.some(r=>routes.includes(r))&&!layers.stations.querySelector(`[data-id="${s.id}"]`)).forEach(s=>{dot(s);layers.stations.lastChild.setAttribute('data-id',s.id);});
    await sleep(340);
  }
  line(`<b>${data.rail_station_count}</b> rail stations · <b>${data.silver_station_count}</b> Silver Line stops · <b>${data.pattern_count}</b> stop patterns, straight from the MBTA timetable`);
  tag(`${data.bus.routes.length} bus connector routes`,'#FFC72C');
  for(const b of [bus21,bus109,bus8])if(b.options[0])drawLeg(b.options[0].legs[0],500,{color:'#FFC72C',dash:'2 7',width:3.5});
  await at(8000);

  /* 8.0 – 12.0 s  ride */
  clear();line(null);speed=0.12;tag('Ride · the path follows the official shape',colors.Red);
  flyTo(ride.options[0].legs[0].geometry,1.2);
  const r=evRide.legs[0];
  line(`Alewife → Braintree. Pick two stations or drag along the track; the evaluator boards the <b>real train</b>: ${fmt(r.departure)} → ${fmt(r.arrival)}.`);
  stats([`<b>${dur(r.travel_seconds)}</b> scheduled`,`<b>${r.segments?.length?r.segments.length+1:ride.options[0].legs[0].stations.length}</b> station calls`,`trip <b>${esc(r.trip_id)}</b>`]);
  await drawLeg(ride.options[0].legs[0],1400);label('place-alfcl');label('place-brntn');
  const segs=r.segments||[];for(const s of [segs[5],segs[12]].filter(Boolean)){await tip(stations[s.to].point,`<b>${esc(names[s.from])} → ${esc(names[s.to])}</b>${dur(s.seconds)} · ${fmt(s.departure)} → ${fmt(s.arrival)}<br><small>hover any segment</small>`,650);}
  await at(12000);

  /* 12.0 – 15.5 s  transfer */
  clear();tag('Transfers · GTFS pathways, priced honestly',colors['Green-B']);
  const xl=xfer.options[0].legs;flyTo(xl.flatMap(l=>l.geometry),1.25);
  const tr=evX.legs.find(l=>l.transfer?.street_level);
  line(`Boston College → Heath Street. Copley forbids the in-station reversal, so the plan prices a <b>street-level transfer</b> instead of refusing.`);
  stats([`<b>${xl.length-1}</b> transfer`,tr?`<b>${dur(tr.transfer_seconds)}</b> ${esc(tr.transfer.via_names?.join(' → ')||'exit · cross · re-enter')}`:'',`finish <b>${fmt(evX.summary.finish)}</b>`].filter(Boolean));
  for(const l of xl)await drawLeg(l,800);
  await tip(stations['place-coecl'].point,`<b>Copley</b>exit Boylston St, re-enter Dartmouth St<br><small>${tr?dur(tr.transfer_seconds):'3m'} · estimated street transfer</small>`,900);
  await at(15500);

  /* 15.5 – 20.0 s  run on real streets */
  clear();tag('Run · Google street route',  '#b48cff');
  const railMin=evRail?Math.round((evRail.summary.finish-evRail.legs[0].start_time)/60):null,runMin=Math.round(evRun.legs[0].travel_seconds/60);
  line(`Fenway → Saint Mary's Street: two Green branches 270 m apart. Auto times a <b>street run</b> against the rail paths and puts the fastest first.`);
  stats([`run <b>${dur(evRun.legs[0].travel_seconds)}</b> · ${(evRun.legs[0].distance/1000).toFixed(2)} km`,evRail?`rail <b>${railMin}m</b> via ${esc(names[evRail.legs[0].to])}`:'',street?`Google walking <b>${dur(street.provider_seconds)}</b>`:''].filter(Boolean));
  if(gm){await googleRun(runLeg,1600);await at(19500);$('gmap').classList.remove('on');}
  else{flyTo([stations['place-fenwy'].point,stations['place-smary'].point],2.2,2600,0.14);if(evRail)for(const l of railFR.options[0].legs)await drawLeg(l,500);await drawLeg(runLeg,1200);label('place-fenwy');label('place-smary');layers.labels.lastChild.setAttribute('y',xy(stations['place-smary'].point)[1]+view[2]/40);}
  await at(20000);

  /* 20.0 – 23.0 s  bus + silver */
  clear();tag('Bus + Silver Line · legal connectors','#FFC72C');
  const bl=bus21.options[0].legs[0],sll=sl3.options[0].legs[0];flyTo([...bl.geometry,...sll.geometry],1.15);
  line(`Bus 21 jumps Orange → Red without the downtown trunk; SL3 rides to Chelsea with its own coverage count. Buses never count as stations.`);
  stats([`bus 21 <b>${dur(evBus.legs[0].travel_seconds)}</b> + ${dur(evBus.legs[0].wait_seconds)} wait`,`SL3 <b>${dur(evSl.legs[0].travel_seconds)}</b> · ${evSl.silver_covered.length} Silver stops`]);
  await drawLeg(bl,800);label('place-forhl');label('place-asmnl');tag('Silver Line · part of the record',colors['741']);await drawLeg(sll,800);label('place-chels');
  await at(23000);

  /* 23.0 – 27.6 s  the whole day */
  clear();stats(null);tag('The whole day · every leg, live-timed','#8fd3c7');speed=0.08;target=fitAspect([...FULL]);
  line(`${day.legs.length} legs, ${day.legs.filter(l=>l.mode==='run').length} of them on foot. Start ${fmt(evDay.legs[0].start_time)}, last platform <b>${fmt(evDay.summary.finish)}</b>.`);
  const seen=new Set();clock(evDay.legs[0].start_time);count(0,data.rail_station_count);
  for(const [i,l] of day.legs.entries()){drawLeg(l,260,{width:4.5});(l.stations||[l.from,l.to]).forEach(s=>{if(stations[s]?.kind!=='silver')seen.add(s);});clock(evDay.legs[i].arrival);count(Math.min(seen.size,evDay.covered.length),data.rail_station_count);await sleep(105);}
  count(evDay.covered.length,data.rail_station_count);
  const an=await analysis;
  if(an&&an.repeated_pieces?.length){
    const rep=new Set(an.repeated_pieces.map(p=>`${p.leg}:${p.segment}`));
    evDay.legs.forEach((l,i)=>(l.segments||[]).forEach((s,k)=>{if(rep.has(`${i}:${k}`))layers.flash.append(el('polyline',{points:s.geometry.map(xy).join(' '),fill:'none',stroke:'#ff5a4e','stroke-width':3,'stroke-dasharray':'3 5','vector-effect':'non-scaling-stroke'}));}));
    const sc=an.stretches.flatMap(s=>s.shortcuts).sort((a,b)=>(b.proposal?.saves_seconds||b.saves_seconds)-(a.proposal?.saves_seconds||a.saves_seconds))[0];
    tag('Backtracking check · the speedrun view','#ff5a4e');
    line(`<b>${dur(an.backtrack_seconds)}</b> of this plan re-rides track it already covered (dotted red).${sc?` Best shortcut: ${esc(sc.label)} — saves <b>${dur(sc.proposal?.saves_seconds||sc.saves_seconds)}</b>, one click to approve.`:''}`);
  }
  await at(27600);

  /* 27.6 – 30.5 s  end card */
  ['tag','line','clock','count','stats'].forEach(id=>$(id).hidden=true);$('end').hidden=false;
  await at(30500);document.body.dataset.done='1';
}
async function fullDay(){
  /* The rehearsal plan from the studio, rebuilt live from the timetable: every ride is the real option for its pair. */
  const n=Object.fromEntries(data.stations.map(s=>[s.name,s.id]));
  const plan=[['Green-D','Union Square','Fenway'],['run','Fenway',"Saint Mary's Street"],['Green-C',"Saint Mary's Street",'Cleveland Circle'],['run','Cleveland Circle','Boston College'],['Green-B','Boston College','Copley'],['Green-E','Copley','Heath Street'],['run','Heath Street','Jackson Square'],['Orange','Jackson Square','Forest Hills'],['Orange','Forest Hills','Downtown Crossing'],['Red','Downtown Crossing','Ashmont'],['Mattapan','Ashmont','Mattapan'],['Mattapan','Mattapan','Ashmont'],['Red','Ashmont','Savin Hill'],['Red','Savin Hill','JFK/UMass'],['Red','JFK/UMass','Braintree'],['Red','Braintree','Downtown Crossing'],['Orange','Downtown Crossing','Oak Grove'],['Orange','Oak Grove','Sullivan Square'],['run','Sullivan Square','East Somerville'],['Green-E','East Somerville','Medford/Tufts'],['Green-E','Medford/Tufts','East Somerville'],['run','East Somerville','Union Square'],['Green-D','Union Square','Arlington'],['run','Arlington','Charles/MGH'],['Red','Charles/MGH','Alewife'],['Red','Alewife','Charles/MGH'],['run','Charles/MGH','Bowdoin'],['Blue','Bowdoin','Wonderland']];
  const parts=await Promise.all(plan.map(async([route,a,b])=>{
    const from=n[a],to=n[b];
    if(route==='run')return [{mode:'run',from,to,geometry:[stations[from].point,stations[to].point],geometry_source:'straight_line_sketch'}];
    const o=(await path(from,to,{route})).options;return (o.find(x=>x.legs.length===1)||o[0]).legs;
  }));
  return {legs:parts.flat()};
}
(async()=>{
  try{
    data=await api('/api/network');stations=Object.fromEntries(data.stations.map(s=>[s.id,s]));
    colors=Object.fromEntries([...data.routes,...(data.bus?.routes||[])].map(r=>[r.id,r.color]));names=Object.fromEntries(data.stations.map(s=>[s.id,s.name]));
    boot();await film();
  }catch(error){$('title').hidden=false;$('title').querySelector('p').textContent='Live data unavailable: '+error.message;document.body.dataset.done='1';}
})();
