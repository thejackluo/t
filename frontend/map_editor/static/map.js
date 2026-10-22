/* Google Maps canvas plus a key-free geographic preview of our own GTFS geometry. */
const NS = 'http://www.w3.org/2000/svg';
const xy = p => [(p[1] + 71.1) * 82000, (42.35 - p[0]) * 111000];
const ll = p => [42.35 - p[1] / 111000, p[0] / 82000 - 71.1];
const latLng = p => ({lat: p[0], lng: p[1]});
function svgEl(tag, attrs = {}, text) {
  const node = document.createElementNS(NS, tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  if (text !== undefined) node.textContent = text;
  return node;
}

export class RouteMap {
  constructor(host, network, callbacks) {
    this.host = host; this.data = network; this.callbacks = callbacks;
    this.colors = Object.fromEntries(network.routes.map(r => [r.id, r.color]));
    this.stations = Object.fromEntries(network.stations.map(s => [s.id, s]));
    this.state = {legs: [], preview: [], covered: new Set(), from: '', to: '', edit: -1};
    this.polylines = []; this.googleMap = null; this.googleLoading = false;
    this.showPreview();
    this.observer = new ResizeObserver(() => {if (!this.googleMap) this.drawSVG();});
    this.observer.observe(host);
  }

  bounds(points) {
    const positions = points.map(xy);
    const xs = positions.map(p => p[0]), ys = positions.map(p => p[1]);
    const left = Math.min(...xs), top = Math.min(...ys);
    const width = Math.max(1000, Math.max(...xs) - left), height = Math.max(1000, Math.max(...ys) - top);
    return [left - width * .14, top - height * .14, width * 1.28, height * 1.28];
  }

  showPreview() {
    this.googleMap = null;
    this.host.replaceChildren();
    this.svg = svgEl('svg', {role: 'group', 'aria-label': 'Geographic MBTA track preview. Select stations with pointer or endpoint selectors.'});
    this.host.append(this.svg);
    this.view = this.bounds(this.data.stations.map(s => s.point));
    this.svg.addEventListener('wheel', event => {
      event.preventDefault();
      const p = this.svgPoint(event);
      const factor = event.deltaY > 0 ? 1.16 : 1 / 1.16;
      this.zoom(factor, p);
    }, {passive: false});
    this.svg.addEventListener('pointerdown', e => this.pointerDown(e));
    this.svg.addEventListener('pointermove', e => this.pointerMove(e));
    this.svg.addEventListener('pointerup', e => this.pointerUp(e));
    this.svg.addEventListener('pointercancel', () => {this.gesture = null; this.drawSVG();});
    this.svg.addEventListener('keydown', e => {
      const target = e.target.closest('[data-station]');
      if (target && (e.key === 'Enter' || e.key === ' ')) {e.preventDefault(); this.callbacks.pick(target.dataset.station);}
    });
    this.drawSVG();
  }

  svgPoint(event) {
    const point = new DOMPoint(event.clientX, event.clientY);
    const p = point.matrixTransform(this.svg.getScreenCTM().inverse());
    return [p.x, p.y];
  }

  pixelScale() {
    return Math.max(this.view[2] / Math.max(1, this.host.clientWidth), this.view[3] / Math.max(1, this.host.clientHeight));
  }

  pointerDown(e) {
    if (e.button !== 0) return;
    const station = e.target.closest('[data-station]')?.dataset.station;
    const waypoint = e.target.closest('[data-waypoint]')?.dataset.waypoint;
    this.gesture = {station, waypoint: waypoint === undefined ? null : Number(waypoint),
      client: [e.clientX, e.clientY], point: this.svgPoint(e), view: [...this.view], moved: false};
    this.svg.setPointerCapture(e.pointerId);
  }

  pointerMove(e) {
    const g = this.gesture;
    if (!g) return;
    if (Math.hypot(e.clientX - g.client[0], e.clientY - g.client[1]) > 5) g.moved = true;
    if (!g.moved) return;
    const p = this.svgPoint(e);
    if (g.station) {
      if (!this.ghost) {
        this.ghost = svgEl('line', {stroke: '#192f3c', 'stroke-width': 3, 'stroke-dasharray': '6 5', 'vector-effect': 'non-scaling-stroke', 'pointer-events': 'none'});
        this.svg.append(this.ghost);
      }
      const a = xy(this.stations[g.station].point);
      ['x1','y1','x2','y2'].forEach((k,i) => this.ghost.setAttribute(k, [...a,...p][i]));
    } else if (g.waypoint !== null) {
      const handle = this.svg.querySelector(`[data-waypoint="${g.waypoint}"]`);
      if (handle) {handle.setAttribute('cx', p[0]); handle.setAttribute('cy', p[1]);}
    } else {
      const scale = this.pixelScale();
      this.view = [g.view[0] - (e.clientX - g.client[0]) * scale, g.view[1] - (e.clientY - g.client[1]) * scale, g.view[2], g.view[3]];
      this.svg.setAttribute('viewBox', this.view.join(' '));
    }
  }

  pointerUp(e) {
    const g = this.gesture;
    if (!g) return;
    const p = this.svgPoint(e);
    this.gesture = null;
    if (this.svg.hasPointerCapture(e.pointerId)) this.svg.releasePointerCapture(e.pointerId);
    if (g.station) {
      if (!g.moved) this.callbacks.pick(g.station);
      else {
        const station = this.nearest(p);
        if (station && station !== g.station) this.callbacks.drag(g.station, station);
      }
    } else if (g.waypoint !== null && g.moved) {
      const leg = this.state.legs[this.state.edit];
      const geometry = leg.geometry.map(p => [...p]);
      geometry[g.waypoint] = ll(p).map(n => +n.toFixed(6));
      this.callbacks.foot(this.state.edit, geometry);
    } else if (!g.moved && this.state.edit >= 0) {
      this.addWaypoint(ll(p));
    }
    this.ghost = null;
    this.drawSVG();
  }

  nearest(p) {
    let found = null, best = 22 * this.pixelScale();
    this.data.stations.forEach(s => {const q = xy(s.point), d = Math.hypot(q[0] - p[0], q[1] - p[1]); if(d < best){best = d; found = s.id;}});
    return found;
  }

  addWaypoint(point) {
    const leg = this.state.legs[this.state.edit];
    if (!leg || leg.mode === 'ride') return;
    const geometry = leg.geometry.map(p => [...p]), p = xy(point);
    let best = Infinity, insertion = 1;
    for (let i = 1; i < geometry.length; i++) {
      const a = xy(geometry[i-1]), b = xy(geometry[i]);
      const dx = b[0]-a[0], dy = b[1]-a[1], t = Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy || 1)));
      const d = Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);
      if(d<best){best=d;insertion=i;}
    }
    geometry.splice(insertion,0,point.map(n=>+n.toFixed(6)));
    this.callbacks.foot(this.state.edit, geometry);
  }

  setState(state) {
    this.state = state;
    if(this.googleMap) this.drawGoogle(); else this.drawSVG();
  }

  zoom(factor, center) {
    if(this.googleMap){this.googleMap.setZoom(this.googleMap.getZoom()+(factor<1?1:-1));return;}
    if(this.view[2]*factor<250 || this.view[2]*factor>150000)return;
    center ||= [this.view[0]+this.view[2]/2,this.view[1]+this.view[3]/2];
    this.view = [center[0]+(this.view[0]-center[0])*factor,center[1]+(this.view[1]-center[1])*factor,this.view[2]*factor,this.view[3]*factor];
    this.drawSVG();
  }

  fit() {
    const legs = this.state.preview.length ? this.state.preview : this.state.legs;
    const points = legs.length ? legs.flatMap(l=>l.geometry) : this.data.stations.map(s=>s.point);
    if(this.googleMap){const b=new google.maps.LatLngBounds();points.forEach(p=>b.extend(latLng(p)));this.googleMap.fitBounds(b,60);}
    else{this.view=this.bounds(points);this.drawSVG();}
  }

  drawSVG() {
    if(!this.svg || this.googleMap)return;
    this.svg.replaceChildren();
    this.svg.setAttribute('viewBox',this.view.join(' '));
    const scale=this.pixelScale();
    const bg=svgEl('rect',{x:-150000,y:-150000,width:300000,height:300000,fill:'#edf2ee'});
    this.svg.append(bg);
    // Quiet geographic grid; no external tiles or invented street network.
    const grid=svgEl('g',{stroke:'#dfe7e0','stroke-width':1,'vector-effect':'non-scaling-stroke'});
    for(let x=-30000;x<30000;x+=2500)grid.append(svgEl('line',{x1:x,y1:-30000,x2:x,y2:30000,'vector-effect':'non-scaling-stroke'}));
    for(let y=-30000;y<30000;y+=2500)grid.append(svgEl('line',{x1:-30000,y1:y,x2:30000,y2:y,'vector-effect':'non-scaling-stroke'}));
    this.svg.append(grid);
    const path=(geometry,attrs)=>svgEl('polyline',{points:geometry.map(xy).map(p=>p.join(',')).join(' '),fill:'none','stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke',...attrs});
    this.data.lines.forEach(l=>this.svg.append(path(l.geometry,{stroke:this.colors[l.route],'stroke-width':2.3,opacity:.3})));
    const layers=[...this.state.legs.map((l,i)=>({l,i,preview:false})),...this.state.preview.map(l=>({l,i:-1,preview:true}))];
    layers.forEach(({l,i,preview})=>{
      const foot=l.mode!=='ride';
      this.svg.append(path(l.geometry,{stroke:'#fff','stroke-width':preview?9:8,opacity:.95}));
      this.svg.append(path(l.geometry,{stroke:foot?'#7952c7':this.colors[l.route],'stroke-width':preview?5:4.5,
        'stroke-dasharray':foot?'6 5':'none',opacity:preview?1:.9}));
      if(i>=0){const p=xy(l.geometry[Math.floor(l.geometry.length/2)]);this.svg.append(svgEl('circle',{cx:p[0],cy:p[1],r:9*scale,fill:'#193342',stroke:'white','stroke-width':1.5,'vector-effect':'non-scaling-stroke'}));this.svg.append(svgEl('text',{x:p[0],y:p[1]+3.3*scale,'text-anchor':'middle','font-size':10*scale,fill:'white','font-weight':700,'pointer-events':'none'},String(i+1)));}
    });
    this.data.stations.forEach(s=>{
      const p=xy(s.point),selected=s.id===this.state.from||s.id===this.state.to,covered=this.state.covered.has(s.id);
      const group=svgEl('g',{'data-station':s.id,role:'button',tabindex:0,'aria-label':`${s.name}; ${s.routes.join(', ')}${covered?'; planned rail visit':''}`,class:'station-handle'});
      group.append(svgEl('circle',{cx:p[0],cy:p[1],r:(selected?7:4.2)*scale,fill:selected?'#ffdf80':covered?'#126a61':'#fff',stroke:selected?'#172c3e':covered?'#fff':'#50646b','stroke-width':selected?2.5:1.5,'vector-effect':'non-scaling-stroke'}));
      group.append(svgEl('title',{},`${s.name} · ${s.routes.join(', ')}`));
      if(selected||this.view[2]<11000||s.routes.length>1||['place-alfcl','place-brntn','place-wondl','place-forhl','place-river','place-asmnl'].includes(s.id)){
        group.append(svgEl('text',{x:p[0]+8*scale,y:p[1]-5*scale,class:'station-label',style:`font-size:${10*scale}px;stroke-width:${3*scale}px`},s.name));
      }
      this.svg.append(group);
    });
    const edit=this.state.legs[this.state.edit];
    if(edit && edit.mode!=='ride')edit.geometry.forEach((point,i)=>{if(i===0||i===edit.geometry.length-1)return;const p=xy(point);this.svg.append(svgEl('circle',{'data-waypoint':i,cx:p[0],cy:p[1],r:6*scale,fill:'#7952c7',stroke:'white','stroke-width':2,'vector-effect':'non-scaling-stroke',style:'cursor:move'}));});
  }

  async connectGoogle(key) {
    if(this.googleMap)return;
    if(this.googleLoading)throw Error('Google Maps is already loading.');
    if(!key)throw Error('Enter your Google Maps browser key. The track preview and My Maps exports work without it.');
    this.googleLoading=true;
    try{
      await new Promise((resolve,reject)=>{
        if(window.google?.maps?.Map){resolve();return;}
        window.initTRunMap=resolve;
        window.gm_authFailure=()=>{this.overlay?.setMap(null);this.polylines.forEach(p=>p.setMap(null));this.showPreview();this.callbacks.googleError('Google rejected this browser key or its configuration. Check Maps JavaScript API, billing, and localhost referrer restrictions.');reject(Error('Google Maps authentication failed.'));};
        const script=document.createElement('script');
        script.src='https://maps.googleapis.com/maps/api/js?'+new URLSearchParams({key,callback:'initTRunMap',loading:'async',v:'weekly'});
        script.onerror=()=>reject(Error('Could not reach Google Maps.'));
        document.head.append(script);
      });
      this.host.replaceChildren();
      this.googleMap=new google.maps.Map(this.host,{center:{lat:42.35,lng:-71.09},zoom:11,mapTypeControl:false,streetViewControl:false,fullscreenControl:true,clickableIcons:false,gestureHandling:'greedy'});
      new google.maps.TransitLayer().setMap(this.googleMap);
      const owner=this;
      class Stations extends google.maps.OverlayView{
        onAdd(){
          this.root=document.createElement('div');this.root.style.position='absolute';this.buttons=new Map();
          owner.data.stations.forEach(s=>{
            const b=document.createElement('button');b.className='gm-station';b.title=`${s.name} · ${s.routes.join(', ')}`;b.setAttribute('aria-label',b.title);
            const label=document.createElement('span');label.className='label';label.textContent=s.name;b.append(label);
            b.addEventListener('click',e=>e.stopPropagation());
            b.addEventListener('pointerdown',e=>{
              e.stopPropagation();e.preventDefault();b.setPointerCapture(e.pointerId);this.start={station:s.id,x:e.clientX,y:e.clientY};
            });
            b.addEventListener('pointerup',e=>{
              e.stopPropagation();if(!this.start)return;
              const a=this.start;this.start=null;
              if(Math.hypot(e.clientX-a.x,e.clientY-a.y)<7){owner.callbacks.pick(s.id);return;}
              const rect=owner.host.getBoundingClientRect(),point=new google.maps.Point(e.clientX-rect.left,e.clientY-rect.top);
              let target=null,best=25;
              owner.data.stations.forEach(t=>{const p=this.getProjection().fromLatLngToContainerPixel(new google.maps.LatLng(...t.point));const d=Math.hypot(p.x-point.x,p.y-point.y);if(d<best){best=d;target=t.id;}});
              if(target&&target!==a.station)owner.callbacks.drag(a.station,target);
            });
            b.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();owner.callbacks.pick(s.id);}});
            this.root.append(b);this.buttons.set(s.id,b);
          });
          google.maps.OverlayView.preventMapHitsAndGesturesFrom(this.root);
          this.getPanes().overlayMouseTarget.append(this.root);
        }
        draw(){if(!this.root)return;const p=this.getProjection();owner.data.stations.forEach(s=>{const b=this.buttons.get(s.id),position=p.fromLatLngToDivPixel(new google.maps.LatLng(...s.point));b.style.left=position.x+'px';b.style.top=position.y+'px';b.classList.toggle('covered',owner.state.covered.has(s.id));b.classList.toggle('selected',s.id===owner.state.from||s.id===owner.state.to);});}
        onRemove(){this.root?.remove();}
      }
      this.overlay=new Stations();this.overlay.setMap(this.googleMap);
      this.googleMap.addListener('click',e=>{if(this.state.edit>=0)this.addWaypoint([e.latLng.lat(),e.latLng.lng()]);});
      this.drawGoogle();this.fit();
    }finally{this.googleLoading=false;}
  }

  drawGoogle(){
    this.polylines.forEach(p=>{google.maps.event.clearInstanceListeners(p);p.setMap(null);});this.polylines=[];
    const add=(geometry,options)=>{const p=new google.maps.Polyline({map:this.googleMap,path:geometry.map(latLng),geodesic:false,clickable:false,...options});this.polylines.push(p);return p;};
    this.data.lines.forEach(l=>add(l.geometry,{strokeColor:this.colors[l.route],strokeOpacity:.28,strokeWeight:3,zIndex:1}));
    const layers=[...this.state.legs.map((l,i)=>({l,i})),...this.state.preview.map(l=>({l,i:-1}))];
    layers.forEach(({l,i})=>{
      const foot=l.mode!=='ride',editable=foot&&i===this.state.edit;
      add(l.geometry,{strokeColor:'white',strokeWeight:9,strokeOpacity:.9,zIndex:2});
      const poly=add(l.geometry,{strokeColor:foot?'#7952c7':this.colors[l.route],strokeWeight:5,strokeOpacity:1,zIndex:3,editable,clickable:editable,
        icons:foot?[{icon:{path:'M 0,-1 0,1',strokeOpacity:1,scale:3},offset:'0',repeat:'12px'}]:[{icon:{path:google.maps.SymbolPath.FORWARD_CLOSED_ARROW,scale:2},offset:'65%'}]});
      if(editable){
        const path=poly.getPath();let timer;
        const change=()=>{clearTimeout(timer);timer=setTimeout(()=>{
          if(this.state.legs[i]?.id!==l.id||this.state.edit!==i)return;
          const points=path.getArray().map(p=>[+p.lat().toFixed(6),+p.lng().toFixed(6)]);
          // Station anchors are fixed even while the interior foot path is editable.
          points[0]=this.stations[l.from].point;points[points.length-1]=this.stations[l.to].point;
          this.callbacks.foot(i,points);
        },250);};
        ['set_at','insert_at','remove_at'].forEach(event=>path.addListener(event,change));
      }
    });
    this.overlay?.draw();
  }

  async suggestFoot(index){
    if(!this.googleMap)throw Error('Connect Google Maps first to request a street-route suggestion.');
    const leg=this.state.legs[index];
    const {Route}=await google.maps.importLibrary('routes');
    const {routes}=await Route.computeRoutes({origin:latLng(this.stations[leg.from].point),destination:latLng(this.stations[leg.to].point),travelMode:'WALKING',fields:['path']});
    if(this.state.legs[index]?.id!==leg.id)throw Error('The segment changed while Google was finding its route. Try again.');
    if(!routes?.length)throw Error('No pedestrian route returned. Check entrances or draw a path manually.');
    const points=routes[0].path.map(p=>[typeof p.lat==='function'?p.lat():p.lat,typeof p.lng==='function'?p.lng():p.lng]);
    points[0]=this.stations[leg.from].point;points[points.length-1]=this.stations[leg.to].point;
    this.callbacks.foot(index,points,'google_routes');
  }
}
