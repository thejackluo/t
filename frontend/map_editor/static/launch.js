/* Film-specific presentation of the real studio APIs. Fixed service date for reproducible rehearsal timing. */
'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=s=>s==null?'—':String(Math.floor(s/3600)%24).padStart(2,'0')+':'+String(Math.floor(s%3600/60)).padStart(2,'0');
const dur=s=>s==null?'—':s>=3600?Math.floor(s/3600)+'h '+Math.round(s%3600/60)+'m':Math.round(s/60)+'m';
const clamp=n=>Math.max(0,Math.min(1,n));
const ease=n=>{n=clamp(n);return n*n*(3-2*n);};
const lerp=(a,b,t)=>a+(b-a)*t;
const NS='http://www.w3.org/2000/svg',WORLD=1048576,W=1920,H=1080,DURATION=60;
const params=new URLSearchParams(location.search);
const el=(tag,attrs={})=>{const n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);return n;};
async function api(url,body){
  const r=await fetch(url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();if(!r.ok)throw Error(j.error||r.statusText);return j;
}
function project(p){const sin=Math.sin(p[0]*Math.PI/180);return [(p[1]+180)/360*WORLD,(.5-Math.log((1+sin)/(1-sin))/(4*Math.PI))*WORLD];}
function unproject(p){return {lat:Math.atan(Math.sinh(Math.PI*(1-2*p[1]/WORLD)))*180/Math.PI,lng:p[0]/WORLD*360-180};}
let network,stations,colors,date,svg,root,groups,googleMap=null,mapOK=false,frame,ready=false;
let elapsed=0,playing=false,last=0,scene=-1,offset=0;
let camera,fullCamera,scale=1,sceneStartCamera,sceneTarget;
let day,dayEv,run,runEv,rail,railEv,bus,busEv,silver,silverEv,transfer,transferEv,analysis,sharedURL;
const drawings=[],dots=[],labels=[];
const groupHidden=new Set();
const cuts=[0,9,16,23,30,36,44,51,60];
const name=id=>stations[id]?.name||id;
const option=(a,b,o={})=>api('/api/options?'+new URLSearchParams({from:a,to:b,date,time:o.time||'08:00',route:o.route||'',mode:o.mode||'rail'}));
const evaluate=(legs,time='08:00')=>api('/api/evaluate',{date,time,legs});
const family=r=>r?.startsWith('Green')?'Green':/^\d+$/.test(r||'')?'Silver':r==='Mattapan'?'Red':r;
function color(leg){return leg.mode!=='ride'?'#bca1f7':leg.kind==='bus'?'#ffc72c':leg.route==='Blue'?'#4081db':leg.route?.startsWith('Green')?'#00ad67':family(leg.route)==='Silver'?'#a1afb7':colors[leg.route]||'#9edac9';}
function fitted(points,pad=1.35,maximumZoom=14.3){
  const pts=points.map(project),xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);
  const dx=(Math.max(...xs)-Math.min(...xs))*pad,dy=(Math.max(...ys)-Math.min(...ys))*pad;
  const z=Math.min(maximumZoom,Math.log2(Math.min(1170/Math.max(dx,1e-6),790/Math.max(dy,1e-6))*WORLD/256));
  const s=256*Math.pow(2,z)/WORLD;
  // Keep the journey in the unobstructed map area, right of the product panel.
  return [(Math.min(...xs)+Math.max(...xs))/2-220/s,(Math.min(...ys)+Math.max(...ys))/2-15/s,z];
}
function fitFilm(){const s=Math.min(innerWidth/W,innerHeight/H);$('film').style.transform='scale('+s+')';$('film').style.left=((innerWidth-W*s)/2)+'px';$('film').style.top=((innerHeight-H*s)/2)+'px';}
function applyCamera(c){
  camera=c;scale=256*Math.pow(2,c[2])/WORLD;
  root.setAttribute('transform','translate('+(W/2-c[0]*scale)+' '+(H/2-c[1]*scale)+') scale('+scale+')');
  for(const d of dots)d.node.setAttribute('r',d.radius/scale);
  for(const l of labels){l.node.setAttribute('font-size',18/scale);l.node.setAttribute('stroke-width',5/scale);l.node.setAttribute('x',l.point[0]+12/scale);l.node.setAttribute('y',l.point[1]+l.dy/scale);}
  if(googleMap)googleMap.moveCamera({center:unproject(c),zoom:c[2]});
}
function boot(){
  fitFilm();addEventListener('resize',fitFilm);
  svg=el('svg',{viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'MBTA route rehearsal, drawn along official track shapes'});
  $('stage').append(svg);root=el('g');svg.append(root);groups={};
  for(const k of ['tracks','legs','repeats','stations','labels','pencil']){groups[k]=el('g');root.append(groups[k]);}
  fullCamera=fitted(network.stations.map(s=>s.point),1.15,12);camera=[...fullCamera];applyCamera(camera);
}
function addPath(geometry,{layer='legs',stroke='#fff',width=5,dash='',opacity=1,start=0,duration=1,end=61,group,head=true}={}){
  if(!geometry?.length)return;
  const pts=geometry.map(project),lengths=[0];for(let i=1;i<pts.length;i++)lengths.push(lengths[i-1]+Math.hypot(pts[i][0]-pts[i-1][0],pts[i][1]-pts[i-1][1]));
  const node=el('polyline',{fill:'none',stroke,'stroke-width':width,'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke',opacity:0});
  if(dash)node.setAttribute('stroke-dasharray',dash);
  groups[layer].append(node);
  const pencil=head?el('circle',{fill:stroke,stroke:'#eaf3ef','stroke-width':1.5,'vector-effect':'non-scaling-stroke',opacity:0}):null;
  if(pencil)groups.pencil.append(pencil);
  const d={node,pts,lengths,total:lengths.at(-1),start,duration,end,opacity,group,pencil,last:-1};
  drawings.push(d);return d;
}
function partial(d,f){
  if(f===d.last)return;d.last=f;
  if(f<=0){d.node.setAttribute('opacity',0);if(d.pencil)d.pencil.setAttribute('opacity',0);return;}
  const length=d.total*f;let i=1;while(i<d.lengths.length&&d.lengths[i]<length)i++;
  const a=d.pts[Math.max(0,i-1)],b=d.pts[Math.min(i,d.pts.length-1)],den=(d.lengths[i]??d.total)-d.lengths[i-1];
  const k=den?(length-d.lengths[i-1])/den:0,tip=[lerp(a[0],b[0],k),lerp(a[1],b[1],k)];
  d.node.setAttribute('points',d.pts.slice(0,i).concat([tip]).map(p=>p.join(',')).join(' '));d.node.setAttribute('opacity',d.opacity);
  if(d.pencil){d.pencil.setAttribute('cx',tip[0]);d.pencil.setAttribute('cy',tip[1]);d.pencil.setAttribute('r',5/scale);d.pencil.setAttribute('opacity',f<1?1:0);}
}
function addDot(s,t){
  const p=project(s.point),node=el('circle',{cx:p[0],cy:p[1],r:0,fill:s.routes.length>1?'#f1f4f5':'#cbd8df',stroke:'#142330','stroke-width':2,'vector-effect':'non-scaling-stroke',opacity:0});groups.stations.append(node);
  dots.push({node,radius:s.routes.length>1?7:5,start:t,family:family(s.routes[0])});
}
function label(id,start,end,dy=-15){
  const p=project(stations[id].point),n=el('text',{class:'station-label',opacity:0});n.textContent=name(id);groups.labels.append(n);labels.push({node:n,point:p,dy,start,end});
}
function route(leg,start,duration,end=61,extra={}){return addPath(leg.geometry,{stroke:color(leg),width:6,dash:leg.mode!=='ride'?'9 7':leg.kind==='bus'?'3 9':'',start,duration,end,...extra});}
function panel(title,body,status='LIVE TIMETABLE'){return '<div class="panel"><div class="panel-head">'+title+'<span class="status">'+status+'</span></div><div class="panel-body">'+body+'</div></div>';}
function setPanel(html){$('panel').innerHTML=html;$('panel').className='enter';}
function title(kicker,headline){$('eyebrow').textContent=kicker;$('headline').innerHTML=headline;$('chapter').classList.remove('enter');void $('chapter').offsetWidth;$('chapter').classList.add('enter');}
function caption(html){$('caption').innerHTML=html||'';$('caption').className=html?'enter':'hidden';}
function mode(id){document.querySelectorAll('#modes span').forEach(n=>n.classList.toggle('active',n.dataset.mode===id));}
function scoreboard(sec,covered){$('clock').textContent=fmt(sec);$('coverage').innerHTML='<b>'+covered+'</b> / '+network.rail_station_count+' rail stations';}
function field(label,value){return '<div class="field"><small>'+label+'</small><b>'+esc(value)+'</b></div>';}
function miniLeg(leg,ev,i){return '<div class="mini-leg"><span class="num">'+String(i+1).padStart(2,'0')+'</span><span class="route-badge" style="--c:'+color(leg)+'">'+esc(leg.mode==='run'?'RUN':leg.route?.replace('Green-','')||'')+'</span><div class="desc">'+esc(name(leg.to))+'<small>'+esc(name(leg.from))+' → '+dur(ev.travel_seconds)+'</small></div><span class="arrival">'+fmt(ev.arrival)+'</span></div>';}
function metric(value,description){return '<div class="metric"><b>'+value+'</b><span>'+description+'</span></div>';}
function tip(id,html,on){const n=$('tip');if(!on){n.style.opacity=0;return;}const p=project(stations[id].point),x=(p[0]-camera[0])*scale+W/2,y=(p[1]-camera[1])*scale+H/2;n.innerHTML=html;n.style.left=Math.min(1530,Math.max(540,x+18))+'px';n.style.top=Math.min(830,Math.max(155,y+12))+'px';n.style.opacity=1;}

function buildDrawings(){
  const families=[['Red',['Red','Mattapan']],['Orange',['Orange']],['Blue',['Blue']],['Green',['Green-B','Green-C','Green-D','Green-E']],['Silver',['741','742','743','746','749','751']]];
  const stationSeen=new Set();
  families.forEach(([f,rs],i)=>{
    const start=.25+i*1.05;
    // Each shape follows its actual vertex order; points are revealed progressively rather than changing opacity.
    for(const l of network.lines.filter(l=>rs.includes(l.route)))addPath(l.geometry,{layer:'tracks',stroke:color({mode:'ride',route:l.route}),width:3.2,opacity:.52,start,duration:2.1,group:f,head:i<4});
    network.stations.filter(s=>s.routes.some(r=>rs.includes(r))&&!stationSeen.has(s.id)).forEach((s,k)=>{stationSeen.add(s.id);addDot(s,start+.7+(k%18)*.04);});
  });
  day.legs.forEach((l,i)=>{
    const t=36+i*(7/day.legs.length);
    route(l,t,.4,51,{width:5});
  });
  const first=day.parts[0];
  first.forEach(l=>route(l,10.2,2.3,16));
  label('place-unsqu',9,16);label('place-fenwy',11,23,28);
  rail.options[0]?.legs.forEach((l,i)=>route(l,16.2+i*.5,.9,23,{opacity:.45,width:5}));
  route(run,19.5,2,30,{width:7});label(run.to,20,23,-22);
  day.parts[2].forEach(l=>route(l,23,1.3,30));
  day.parts[3].forEach(l=>route(l,24.3,.7,30));
  day.parts[4].forEach(l=>route(l,25,1.5,30));
  day.parts[5].forEach(l=>route(l,26.5,1.5,30));
  label('place-coecl',25.8,30);
  route(bus.options[0].legs[0],31,2,36,{width:6.5});
  route(silver.options[0].legs[0],33,1.6,36,{width:5});
  label('place-forhl',30,36);label('place-asmnl',32,36);label('place-chels',34,36);
  const rep=new Set((analysis?.repeated_pieces||[]).map(p=>p.leg+':'+p.segment));
  dayEv.legs.forEach((l,i)=>(l.segments||[]).forEach((s,k)=>{
    if(rep.has(i+':'+k))addPath(s.geometry,{layer:'repeats',stroke:'#ff796d',width:4,dash:'5 7',start:44,duration:.8,end:51,head:false});
  }));
}
function sceneCamera(i){
  if(i===0)return fullCamera;
  if(i===1)return fitted(day.parts[0].flatMap(l=>l.geometry),1.4,13.5);
  if(i===2)return fitted([...run.geometry,...(rail.options[0]?.legs.flatMap(l=>l.geometry)||[])],1.4,15);
  if(i===3)return fitted(day.parts.slice(2,6).flat(1).flatMap(l=>l.geometry),1.3,13.6);
  if(i===4)return fitted([...bus.options[0].legs[0].geometry,...silver.options[0].legs[0].geometry],1.22,12.6);
  return fullCamera;
}
function enterScene(i){
  scene=i;sceneStartCamera=[...camera];sceneTarget=sceneCamera(i);$('tip').style.opacity=0;
  $('studio').classList.toggle('on',i===7);$('final-brand').classList.toggle('on',i===7);
  $('chapter').classList.toggle('hidden',i===7);$('panel').classList.remove('hidden');
  if(i===0){
    mode(null);title('The Boston challenge','Every station.<br>One <em>continuous clock.</em>');
    setPanel(panel('The record to chase','<h2>Fastest time to travel to all Boston subway stations</h2><div class="rule"><b class="num">01</b><div><strong>Train doors close. Clock starts.</strong><small>Last platform reached. Clock stops. Every wait and foot transfer counts.</small></div></div><div class="rule"><b class="num">02</b><div><strong>Every required station.</strong><small>Stopping public-service rides earn visits. The supplied rules include Silver Line.</small></div></div><div class="rule"><b class="num">03</b><div><strong>Find the connections.</strong><small>Scheduled public transport or on foot. No taxis, bikes or private rides.</small></div></div>','SUPPLIED GUIDELINES'));
    caption('The challenge is not drawing the shortest line.<br>It is catching the <b>right trains</b>, in the right order.');
  }else if(i===1){
    mode('ride');title('01 / Build the journey','From a shared route<br>to the <em>real train.</em>');
    const l=day.legs[0],ev=dayEv.legs[0];
    setPanel(panel('Build a connection',field('From',name(l.from))+field('To',name(l.to))+'<div class="ride-row"><span class="route-badge">D</span>Green-D<span class="time">'+fmt(ev.departure)+' → '+fmt(ev.arrival)+'</span></div>'+metric(dur(ev.travel_seconds),'ride · '+(l.stations?.length||0)+' station calls')+'<div class="subtle">Official MBTA shapes.<br>Calendar, platform and boarding restrictions preserved.</div><div class="button">Add to rehearsal</div>'));
    caption('Ride follows the track. Hover reveals <b>station-by-station timing</b>.');
  }else if(i===2){
    mode('auto');title('02 / Think like a speedrunner','Two branches.<br><em>One short run.</em>');
    const r=runEv.legs[0],railSeconds=railEv?railEv.summary.finish-railEv.legs[0].start_time:null;
    setPanel(panel('Auto · compare arrivals','<h2>Fenway → Saint Mary’s Street</h2><div class="subtle" style="margin-bottom:20px">Same start clock. Rail and running, compared.</div><div class="comparison" id="run-choice"><div class="top"><span>Run <span class="best">FASTEST</span></span><b>'+dur(runEv.summary.finish-r.start_time)+'</b></div><small>'+(r.distance/1000).toFixed(2)+' km · Google pedestrian route<br>Includes entry / exit assumptions</small></div><div class="comparison"><div class="top"><span>Ride via Kenmore</span><b>'+dur(railSeconds)+'</b></div><small>Real departure + wait + transfer</small></div><div class="button" id="run-add">Choose the street shortcut</div>'));
    caption('A few hundred metres on foot can beat a branch change.<br><b>Google streets</b> underneath. Pace-based estimate, not a train time.');
  }else if(i===3){
    mode('ride');title('03 / Price the hidden costs','A transfer is<br><em>part of the race.</em>');
    const tr=transferEv.legs.find(l=>l.transfer?.street_level);
    setPanel(panel('The next connections',day.parts.slice(2,6).flat().map((l,k)=>'<div class="mini-leg"><span class="route-badge" style="--c:'+color(l)+'">'+esc(l.mode==='run'?'RUN':l.route.replace('Green-',''))+'</span><div class="desc">'+esc(name(l.to))+'<small>from '+esc(name(l.from))+'</small></div></div>').join('')+'<div class="diff-plus"><b>Copley · '+dur(tr?.transfer_seconds)+'</b><br>Exit, cross the street, re-enter.<br><small>Estimated street-level change; GTFS forbids the in-station reversal.</small></div>'));
    caption('No impossible platform change.<br>The plan <b>prices the street transfer</b> and recomputes the next train.');
  }else if(i===4){
    mode('bus');title('04 / Use the whole city','Skip the trunk.<br><em>Take the connector.</em>');
    const b=busEv.legs[0],s=silverEv.legs[0];
    setPanel(panel('A crosstown alternative','<h2>Forest Hills → Ashmont</h2><div class="ride-row"><span class="route-badge" style="--c:#997813">21</span>Orange → Red</div>'+metric(dur(b.travel_seconds),'bus ride · '+dur(b.wait_seconds)+' wait')+'<div class="subtle">Scheduled MBTA bus. Access walking included by the evaluator. A bus never earns station coverage.</div><div class="ride-row" style="border-top:1px solid #ffffff18;margin-top:18px"><span class="route-badge" style="--c:#7c878e">SL3</span>South Station → Chelsea</div><div class="subtle">'+dur(s.travel_seconds)+' scheduled ride · '+silverEv.silver_covered.length+' Silver stops, tracked separately.</div>'));
    caption('An alternative to test, <b>not a guaranteed saving</b>.<br>Departure times decide whether the shortcut wins.');
  }else if(i===5){
    mode(null);title('05 / Recompute the whole day','One connected plan.<br><em>Every minute exposed.</em>');
    setPanel(panel('Shared rehearsal · '+day.legs.length+' legs','<div id="live-legs"></div>'+metric(dur(dayEv.summary.elapsed),'planned duration, including preparation')+'<div class="subtle">'+dayEv.covered.length+' / '+network.rail_station_count+' imported rail stations.<br>This candidate is a rehearsal — not a complete record route. Silver and the official station inventory still require reconciliation.</div>'));
    caption('Change one leg and the clock downstream changes with it.<br><b>Rides, waits, runs and transfers</b> — nothing silently disappears.');
  }else if(i===6){
    mode('auto');title('06 / Find wasted motion','The track you rode<br><em>twice has a cost.</em>');
    const sc=analysis?.stretches.flatMap(s=>s.shortcuts||[]).find(s=>s.proposal);
    setPanel(panel('Backtracking check',metric(dur(analysis?.backtrack_seconds),'re-ridden track · '+Math.round((analysis?.backtrack_share||0)*100)+'% of moving time')+'<div class="subtle">Dotted red = a segment already covered.<br>Search bus, rail and running alternatives against the same timetable.</div>'+(sc?'<div class="diff-minus">− legs '+esc(sc.proposal.removed_legs.join(', '))+'</div><div class="diff-plus">+ '+esc(sc.label)+'<br>Finish '+fmt(sc.proposal.finish_before)+' → '+fmt(sc.proposal.finish_after)+'</div><div class="button">Review · saves '+dur(sc.proposal.saves_seconds)+'</div>':'<div class="diff-minus">Repeated track does not automatically mean a faster shortcut exists.</div><div class="diff-plus">This rehearsal has no faster approved proposal at these times.</div>')+'<div class="proof"><i></i>Suggestions are proposals, not magic.</div>'));
    caption('A speedrun is a sequence of <b>testable ideas</b>.<br>Keep the legal visits. Challenge the wasted motion.');
  }else{
    mode(null);$('panel').classList.add('hidden');caption(null);
  }
}
function render(t){
  elapsed=Math.max(0,Math.min(DURATION,t));
  const i=Math.min(7,cuts.findIndex((v,k)=>k<8&&elapsed>=v&&elapsed<cuts[k+1]));
  if(i>=0&&i!==scene)enterScene(i);
  const local=elapsed-cuts[Math.max(0,scene)];
  const k=ease(local/1.7);
  let target=sceneTarget;
  if(scene===2&&local>2.8)target=fitted(run.geometry,2.6,16.2);
  const camK=scene===2&&local>2.8?ease((local-2.8)/1.7):k;
  const start=scene===2&&local>2.8?sceneTarget:sceneStartCamera;
  applyCamera(start.map((v,k)=>lerp(v,target[k],camK)));
  for(const d of drawings){
    const visible=elapsed>=d.start&&elapsed<d.end&&!groupHidden.has(d.group);
    const f=visible?ease((elapsed-d.start)/d.duration):0;
    if(f===1&&d.last===1){if(d.pencil)d.pencil.setAttribute('opacity',0);continue;}partial(d,f);
  }
  for(const d of dots)d.node.setAttribute('opacity',elapsed>=d.start&&!groupHidden.has(d.family)?ease((elapsed-d.start)/.5)*.94:0);
  for(const l of labels)l.node.setAttribute('opacity',elapsed>=l.start&&elapsed<l.end?1:0);
  document.querySelectorAll('.legend-item').forEach((n,j)=>n.classList.toggle('on',elapsed>=j*1.05+.5));
  if(scene===0){scoreboard(28800,0);}
  if(scene===1){
    const ev=dayEv.legs[0],p=ease((elapsed-10.2)/2.3);scoreboard(lerp(ev.departure,ev.arrival,p),Math.round((day.legs[0].stations?.length||0)*p));
    const s=ev.segments?.[5];if(s)tip(s.to,'<strong>'+esc(name(s.from))+' → '+esc(name(s.to))+'</strong>'+dur(s.seconds)+' · '+fmt(s.departure)+' → '+fmt(s.arrival)+'<br><small>Scheduled estimate · MBTA GTFS</small>',local>3.3&&local<5.5);
  }
  if(scene===2){mode(local>3.2?'run':'auto');$('run-choice')?.classList.toggle('selected',local>2.4);if($('run-add'))$('run-add').textContent=local>4.5?'Street shortcut added ✓':'Choose the street shortcut';scoreboard(runEv.summary.finish,dayEv.legs[0].stations.length);}
  if(scene===3){const tr=transferEv.legs.find(l=>l.transfer?.street_level);tip('place-coecl','<strong>Copley · '+dur(tr?.transfer_seconds)+'</strong>Exit Boylston St → re-enter Dartmouth St<br><small>Estimated street-level transfer</small>',local>3.9);}
  if(scene===5){
    const index=Math.min(day.legs.length-1,Math.floor(local/7*day.legs.length));
    const seen=new Set();for(let j=0;j<=index;j++)(dayEv.legs[j].stop_calls||[]).forEach(c=>{if(stations[c.station]?.kind!=='silver')seen.add(c.station);});
    // The evaluator's coverage is authoritative; the display animation is only a progress proxy.
    scoreboard(dayEv.legs[index].arrival,local>=7?dayEv.covered.length:Math.min(dayEv.covered.length,Math.round((index+1)/day.legs.length*dayEv.covered.length)));
    const list=$('live-legs');if(list&&list.dataset.index!==String(index)){list.dataset.index=index;list.innerHTML=day.legs.slice(Math.max(0,index-3),index+1).map((l,j)=>miniLeg(l,dayEv.legs[Math.max(0,index-3)+j],Math.max(0,index-3)+j)).join('');}
  }
  if(scene>=6)scoreboard(dayEv.summary.finish,dayEv.covered.length);
  $('timeline').style.width=(elapsed/DURATION*100)+'%';$('scrub').value=elapsed;$('position').textContent='0:'+String(Math.floor(elapsed)).padStart(2,'0')+' / 1:00';
  if(elapsed>=60){playing=false;document.body.dataset.done='1';$('play').textContent='Replay';}
}
function tick(now){
  if(playing&&ready)render(elapsed+(now-last)/1000);last=now;frame=requestAnimationFrame(tick);
}
function play(){if(!ready)return;if(elapsed>=60){elapsed=0;scene=-1;delete document.body.dataset.done;}last=performance.now();playing=true;$('play').textContent='Pause';}
function pause(){playing=false;$('play').textContent='Play';}
function wireControls(){
  $('play').onclick=()=>playing?pause():play();$('replay').onclick=()=>{elapsed=0;scene=-1;delete document.body.dataset.done;render(0);play();};
  $('scrub').oninput=e=>{pause();scene=-1;render(+e.target.value);};
  document.querySelectorAll('#modes span').forEach((n,i)=>{n.tabIndex=0;n.role='button';n.setAttribute('aria-label','Jump to '+n.textContent+' scene');const fn=()=>{scene=-1;render([16,9,30,19.5][i]);play();};n.onclick=fn;n.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();fn();}};});
  document.querySelectorAll('.legend-item').forEach(n=>{n.tabIndex=0;n.role='button';n.setAttribute('aria-label','Toggle '+n.textContent);n.onclick=()=>{const f=n.dataset.line;groupHidden.has(f)?groupHidden.delete(f):groupHidden.add(f);render(elapsed);};n.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();n.click();}};});
}
const NIGHT=[
  {elementType:'geometry',stylers:[{color:'#172737'}]},
  {elementType:'labels.text.fill',stylers:[{color:'#748c9f'}]},
  {elementType:'labels.text.stroke',stylers:[{color:'#142230'}]},
  {featureType:'poi',stylers:[{visibility:'off'}]},
  {featureType:'road',elementType:'geometry',stylers:[{color:'#263b4d'}]},
  {featureType:'road',elementType:'geometry.stroke',stylers:[{color:'#1b2c3c'}]},
  {featureType:'road.highway',elementType:'geometry',stylers:[{color:'#354a5c'}]},
  {featureType:'transit',stylers:[{visibility:'off'}]},
  {featureType:'water',elementType:'geometry',stylers:[{color:'#0b1722'}]},
  {featureType:'landscape.natural',elementType:'geometry',stylers:[{color:'#182e32'}]}
];
async function loadGoogle(key){
  if(!key)return false;
  return new Promise(resolve=>{
    let timer=setTimeout(()=>resolve(false),12000);
    window.gm_authFailure=()=>{mapOK=false;clearTimeout(timer);$('gmap').style.opacity=0;resolve(false);};
    window.initLaunchMap=()=>{
      try{
        googleMap=new google.maps.Map($('gmap'),{center:unproject(camera),zoom:camera[2],disableDefaultUI:true,clickableIcons:false,gestureHandling:'none',styles:NIGHT,backgroundColor:'#101b26',isFractionalZoomEnabled:true});
        google.maps.event.addListenerOnce(googleMap,'tilesloaded',()=>{clearTimeout(timer);mapOK=true;resolve(true);});
      }catch{clearTimeout(timer);resolve(false);}
    };
    const script=document.createElement('script');script.src='https://maps.googleapis.com/maps/api/js?'+new URLSearchParams({key,callback:'initLaunchMap',loading:'async',v:'weekly'});script.onerror=()=>{clearTimeout(timer);resolve(false);};document.head.append(script);
  });
}
async function fullDay(street){
  const n=Object.fromEntries(network.stations.map(s=>[s.name,s.id]));
  const plan=[['Green-D','Union Square','Fenway'],['run','Fenway',"Saint Mary's Street"],['Green-C',"Saint Mary's Street",'Cleveland Circle'],['run','Cleveland Circle','Boston College'],['Green-B','Boston College','Copley'],['Green-E','Copley','Heath Street'],['run','Heath Street','Jackson Square'],['Orange','Jackson Square','Forest Hills'],['Orange','Forest Hills','Downtown Crossing'],['Red','Downtown Crossing','Ashmont'],['Mattapan','Ashmont','Mattapan'],['Mattapan','Mattapan','Ashmont'],['Red','Ashmont','Savin Hill'],['Red','Savin Hill','JFK/UMass'],['Red','JFK/UMass','Braintree'],['Red','Braintree','Downtown Crossing'],['Orange','Downtown Crossing','Oak Grove'],['Orange','Oak Grove','Sullivan Square'],['run','Sullivan Square','East Somerville'],['Green-E','East Somerville','Medford/Tufts'],['Green-E','Medford/Tufts','East Somerville'],['run','East Somerville','Union Square'],['Green-D','Union Square','Arlington'],['run','Arlington','Charles/MGH'],['Red','Charles/MGH','Alewife'],['Red','Alewife','Charles/MGH'],['run','Charles/MGH','Bowdoin'],['Blue','Bowdoin','Wonderland']];
  const parts=await Promise.all(plan.map(async([route,a,b])=>{
    const from=n[a],to=n[b];
    if(route==='run'){
      let s=from==='place-fenwy'&&to==='place-smary'?street:null;
      if(!s)try{s=await api('/api/foot-route?'+new URLSearchParams({from,to}));}catch{}
      return [{mode:'run',from,to,geometry:s?.geometry||[stations[from].point,stations[to].point],geometry_source:s?'google_routes':'straight_line_sketch',...(s?{provider_seconds:s.provider_seconds}:{})}];
    }
    const opts=(await option(from,to,{route})).options;
    if(!opts?.length)throw Error('No ride available for '+a+' → '+b);
    return (opts.find(x=>x.legs.length===1)||opts[0]).legs;
  }));
  return {parts,legs:parts.flat()};
}
async function shareLink(){
  const s={schema:1,name:'Boston rail rehearsal — launch film',dataset:network.manifest.sha256,ruleset:network.ruleset,date,time:'08:00',assumptions:{run_pace:6,walk_pace:12,buffer:60,access:60,station_change:120},legs:day.legs.map(l=>l.mode==='ride'?{mode:'ride',pattern:l.pattern,start:l.start,end:l.end}:{mode:l.mode,from:l.from,to:l.to})};
  const bytes=new TextEncoder().encode(JSON.stringify(s));
  const packed=await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate-raw'))).arrayBuffer();
  const code='z'+btoa(String.fromCharCode(...new Uint8Array(packed))).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');
  return '/#share='+code;
}
async function prepare(){
  network=await api('/api/network');stations=Object.fromEntries(network.stations.map(s=>[s.id,s]));colors=Object.fromEntries(network.routes.map(r=>[r.id,r.color]));date=network.dates.includes('2026-10-26')?'2026-10-26':network.dates[0];boot();
  const [cfg,street]=await Promise.all([api('/api/config'),api('/api/foot-route?from=place-fenwy&to=place-smary').catch(()=>null)]);
  const gPromise=loadGoogle(cfg.google_maps_key);
  [day,rail,bus,silver,transfer]=await Promise.all([fullDay(street),option('place-fenwy','place-smary',{time:'09:30'}),option('place-forhl','place-asmnl',{mode:'bus',time:'10:30'}),option('place-sstat','place-chels',{route:'743',time:'10:30'}),option('place-lake','place-hsmnl',{time:'09:00'})]);
  run=day.parts[1][0];
  [dayEv,runEv,railEv,busEv,silverEv,transferEv,analysis]=await Promise.all([evaluate(day.legs),evaluate([run],'09:30'),rail.options[0]?evaluate(rail.options[0].legs,'09:30'):null,evaluate(bus.options[0].legs,'10:30'),evaluate(silver.options[0].legs,'10:30'),evaluate(transfer.options[0].legs,'09:00'),api('/api/analyze',{date,time:'08:00',legs:day.legs}).catch(()=>null)]);
  sharedURL=await shareLink();
  const iframe=$('studio-frame');iframe.src=sharedURL;
  // The final reveal is the real, unmodified studio, not a recreated dashboard.
  await Promise.all([gPromise,new Promise(resolve=>{iframe.addEventListener('load',resolve,{once:true});setTimeout(resolve,15000);})]);
  buildDrawings();wireControls();ready=true;document.body.dataset.ready='1';document.body.dataset.map=mapOK?'google':'vector';$('play').disabled=false;
  $('loading').innerHTML='<b>Rehearsal ready · '+date+'</b>'+(mapOK?'Google Maps + live MBTA timetable.':'Vector map · Google Maps unavailable.')+'<br><button id="begin">Play the 60-second film</button>';
  $('begin').onclick=()=>{$('loading').classList.add('hidden');play();};
  render(0);requestAnimationFrame(tick);
  window.launchFilm={start(){document.body.classList.add('recording');$('loading').classList.add('hidden');elapsed=0;scene=-1;render(0);play();},pause,play,seek(t){pause();scene=-1;render(t);},get status(){return {ready,map:mapOK?'google':'vector',seconds:elapsed,playing,date,legs:day.legs.length,coverage:dayEv.covered.length,finish:dayEv.summary.finish,street:run.geometry_source,sharedURL};}};
  if(!params.has('manual')&&!matchMedia('(prefers-reduced-motion: reduce)').matches){$('loading').classList.add('hidden');play();}
}
prepare().catch(error=>{
  $('loading').innerHTML='<b id="error">Could not prepare this rehearsal</b>'+esc(error.message)+'<br><button id="retry">Retry live data</button>';
  $('retry').onclick=()=>location.reload();document.body.dataset.error='1';console.error(error);
});
