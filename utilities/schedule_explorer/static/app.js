'use strict';
const $ = (id) => document.getElementById(id);
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const E = escapeHTML;
let meta, data, state, request = 0, selectedHour = null, shown = 40, activeTab = 'timeline', nextSeconds = null;
const routeName = r => r.startsWith('Green-') ? `Green ${r.slice(-1)}` : r === 'Mattapan' ? 'Mattapan' : `${r} Line`;
const shortDate = d => new Date(`${d}T12:00:00`).toLocaleDateString('en-US', {month:'short', day:'numeric'});
const fullDate = d => new Date(`${d}T12:00:00`).toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'});
function formatTime(s, seconds = false) {
  if (s == null) return '—';
  const hours = Math.floor(s / 3600), h = hours % 24, m = Math.floor(s % 3600 / 60), ss = s % 60;
  return `${h % 12 || 12}:${String(m).padStart(2,'0')}${seconds ? ':'+String(ss).padStart(2,'0') : ''} ${h < 12 ? 'AM' : 'PM'}`;
}
function timeHTML(s) { return s == null ? '—' : `${formatTime(s)}${s >= 86400 ? '<span class="next-day">+1 day</span>' : ''}`; }
const gap = n => n == null ? '—' : `${Number(n.toFixed(1))} min`;
const selectedStation = () => meta.stations.find(s => s.id === state.station);
const params = () => new URLSearchParams(state);
async function api(url) { const r = await fetch(url); if (!r.ok) throw new Error(`Could not load the schedule (${r.status}).`); return r.json(); }
function syncURL() { history.replaceState(null, '', `?${params()}`); }
function setRoute(route) {
  state.route = route;
  if (!selectedStation().routes.includes(route)) state.station = meta.stations.find(s => s.routes.includes(route)).id;
  state.direction = Object.keys(meta.routes.find(r => r.id === route).directions)[0];
  state.destination = ''; selectedHour = null; $('station-search').value = ''; refresh();
}
function renderSidebar() {
  const route = meta.routes.find(r => r.id === state.route);
  document.documentElement.style.setProperty('--line', route.color);
  document.documentElement.style.setProperty('--line-soft', `color-mix(in srgb, ${route.color} 7%, white)`);
  $('route-buttons').innerHTML = meta.routes.map(r => `<button class="route-button ${r.id === state.route ? 'selected' : ''}" data-route="${E(r.id)}" style="--route-color:${r.color}" aria-pressed="${r.id === state.route}"><span class="route-dot"></span>${E(routeName(r.id).replace(' Line',''))}</button>`).join('');
  renderStationList();
  $('direction').innerHTML = Object.entries(route.directions).sort().map(([id,name]) => `<option value="${id}" ${id === state.direction ? 'selected' : ''}>${E(name)} · ${id}</option>`).join('');
}
function renderStationList() {
  const text = $('station-search').value.trim().toLowerCase();
  const stations = meta.stations.filter(s => s.routes.includes(state.route) && (s.name.toLowerCase().includes(text) || s.id.toLowerCase().includes(text))).sort((a,b) => a.name.localeCompare(b.name));
  $('station-count').textContent = `${stations.length} stops`;
  $('station-list').innerHTML = stations.length ? stations.map(s => `<button class="station-item ${s.id === state.station ? 'selected' : ''}" data-station="${E(s.id)}" aria-pressed="${s.id === state.station}">${E(s.name)}</button>`).join('') : '<p class="empty">No matching stations on this line.</p>';
}
function presetDates() {
  const weekdays = [1,5,6,0];
  const target = Math.min(Math.max(Date.parse(state.date+'T12:00:00'), Date.parse(meta.dates[0]+'T12:00:00')),Date.parse(meta.dates.at(-1)+'T12:00:00'));
  const choices = weekdays.map(day => meta.dates.filter(d => new Date(d+'T12:00:00').getDay() === day).sort((a,b) => Math.abs(Date.parse(a+'T12:00:00')-target)-Math.abs(Date.parse(b+'T12:00:00')-target))[0]);
  const thanksgiving = meta.holidays.find(h => h['Holiday name'] === 'Thanksgiving Day' && h['Profile ID']);
  return [['Weekday',choices[0]],['Friday',choices[1]],['Saturday',choices[2]],['Sunday',choices[3]], ...(thanksgiving ? [['Thanksgiving',thanksgiving['Service date']]] : [])];
}
async function refresh() {
  const id = ++request;
  selectedHour = null; shown = 40;
  renderSidebar(); $('service-date').value = state.date;
  $('presets').innerHTML = presetDates().map(([name,day]) => `<button class="preset ${day === state.date ? 'active' : ''}" data-date="${day}" title="${E(fullDate(day))}">${name}</button>`).join('');
  $('load-state').hidden = false; $('load-state').textContent = 'Loading the selected timetable…'; $('content').hidden = true;
  try {
    const response = await api(`/api/station?${params()}`);
    if (id !== request) return;
    data = response; syncURL();
    $('station-name').textContent = selectedStation().name;
    $('station-id').textContent = state.station;
    $('line-badge').textContent = routeName(state.route);
    $('service-pattern').textContent = data.calendar ? `${fullDate(state.date)} · ${data.calendar['Service description']}${data.calendar['Holiday name'] ? ' · '+data.calendar['Holiday name'] : ''}` : 'No published timetable for this date in the loaded snapshot';
    $('destination').innerHTML = '<option value="">Any destination</option>' + [...new Set([...data.destinations, ...(state.destination ? [state.destination] : [])])].map(d => `<option value="${E(d)}" ${d === state.destination ? 'selected' : ''}>${E(d)}${!data.destinations.includes(d) ? ' (not served today)' : ''}</option>`).join('');
    const notice = !data.published ? 'This date is outside the loaded feed. No train times are assumed. Published coverage is '+shortDate(meta.dates[0])+'–'+shortDate(meta.dates.at(-1))+', '+meta.dates[0].slice(0,4)+'.' : data.summary.arrival_only ? 'Trains arrive here in this direction, but these are terminal calls: boarding is not permitted. Try the other direction.' : !data.summary.count ? 'No matching rail departures are scheduled for this selection. Check the direction or destination. Replacement buses are excluded.' : data.calendar['Holiday name'] ? `${data.calendar['Holiday name']}: ${data.calendar['Service description']}. Holiday patterns are applied per route, not assumed to be Sunday service.` : '';
    $('notice').textContent = notice; $('notice').hidden = !notice;
    renderStats(); renderHistogram(); renderWait(); renderComparisons(); renderAbout();
    $('load-state').hidden = true; $('content').hidden = false;
    if (activeTab === 'stations') renderDirectory();
  } catch (error) { if (id === request) { $('load-state').textContent = error.message+' Try refreshing the page.'; $('load-state').classList.add('error'); } }
}
function renderStats() {
  const s = data.summary;
  const cards = [
    ['First train',timeHTML(s.first),'First boardable departure','↗'],
    ['Last train',timeHTML(s.last),'On this service day · +1 = next day','↘'],
    ['Scheduled departures',s.count.toLocaleString(),'Matching your direction & destination','≋'],
    ['Typical scheduled gap',s.median == null ? '—' : `${Number(s.median.toFixed(1))}<small>min</small>`,s.count > 1 ? `Range ${gap(s.min)} – ${gap(s.max)}` : 'Median gap between usable departures','↔']
  ];
  $('stats').innerHTML = cards.map(([label,value,desc,symbol]) => `<article class="stat"><div class="stat-label">${label}<span class="stat-symbol">${symbol}</span></div><div class="stat-value">${value}</div><div class="stat-desc">${desc}</div></article>`).join('');
}
function boardable() { return data.events.filter(e => e.board); }
function renderHistogram() {
  const es = boardable();
  const maxHour = Math.max(26, ...es.map(e => Math.floor(e.seconds/3600)));
  const hours = Array.from({length:maxHour-3},(_,i) => i+4);
  const counts = hours.map(h => es.filter(e => Math.floor(e.seconds/3600) === h).length);
  const max = Math.max(1,...counts);
  $('histogram').innerHTML = hours.map((h,i) => `<button class="hour ${h === selectedHour ? 'selected' : ''}" data-hour="${h}" aria-pressed="${h === selectedHour}" aria-label="${h}:00 service hour: ${counts[i]} departures" title="${h}:00–${h}:59 · ${counts[i]} trains"><span class="hour-count">${counts[i] || ''}</span><span class="hour-bar" style="height:${Math.max(2,counts[i]/max*112)}px;${counts[i] ? '' : 'opacity:.12'}"></span><span class="hour-label">${String(h).padStart(2,'0')}</span></button>`).join('');
  $('clear-hour').hidden = selectedHour == null;
  renderDepartures();
}
function renderDepartures() {
  const all = boardable();
  const events = all.map((e,i) => ({...e, gap:i ? (e.seconds-all[i-1].seconds)/60 : null})).filter(e => selectedHour == null || Math.floor(e.seconds/3600) === selectedHour);
  $('departure-heading').textContent = selectedHour == null ? 'Scheduled departures' : `Departures · ${selectedHour}:00 service hour`;
  $('departure-rows').innerHTML = events.length ? events.slice(0,shown).map(e => `<tr class="${e.seconds === nextSeconds ? 'next-row' : ''}"><td><span class="time-tag" title="Service time ${e.time}">${formatTime(e.seconds,true)}</span>${e.seconds >= 86400 ? '<span class="next-day">+1 day</span>' : ''}${e.seconds === nextSeconds ? '<span class="next-label">NEXT</span>' : ''}</td><td>${E(e.destination)}</td><td>${gap(e.gap)}</td><td class="mono">${E(e.platform)}</td><td class="mono">${E(e.trip)}</td></tr>`).join('') : '<tr><td colspan="5" class="empty">No boardable departures for this selection.<br>Try another hour, direction, destination, or service date.</td></tr>';
  $('departure-count').textContent = `${Math.min(shown,events.length)} of ${events.length} departures · all times America/New_York`;
  $('show-more').hidden = shown >= events.length;
}
function renderWait() {
  const input = $('ready-time').value.trim();
  nextSeconds = null;
  if (!/^\d{2,}:[0-5]\d(?::[0-5]\d)?$/.test(input)) {
    $('wait-result').innerHTML = '<div class="wait-empty error">Enter HH:MM or HH:MM:SS, such as 08:00:00 or 25:15:00.</div>';
    renderDepartures(); return;
  }
  const [h,m,s=0] = input.split(':').map(Number), ready = h*3600+m*60+s;
  const e = boardable().find(e => e.seconds >= ready);
  if (!e) {
    $('wait-result').innerHTML = `<div class="wait-empty">${data.published ? 'No further matching trains on this service day.' : 'No published schedule for this date.'}</div>`;
  } else {
    nextSeconds = e.seconds;
    const delta = e.seconds-ready;
    const wait = delta % 60 ? `${Math.floor(delta/60)}m ${delta%60}s` : String(delta/60);
    $('wait-result').innerHTML = `<div class="wait-main"><span class="wait-number">${wait}</span><span class="wait-unit">${delta%60 ? 'scheduled wait' : 'min scheduled wait'}</span></div><div class="wait-next">${formatTime(e.seconds,true)}${e.seconds >= 86400 ? ' (+1 day)' : ''} → <strong>${E(e.destination)}</strong> · platform ${E(e.platform)}</div>`;
  }
  renderDepartures();
}
function renderComparisons() {
  const filter = $('compare-filter').value;
  const rows = data.comparisons.filter(r => filter === 'all' || (filter === 'holiday' ? r.holiday : ['Saturday','Sunday'].includes(r.day)));
  $('compare-rows').innerHTML = rows.length ? rows.map(r => `<tr class="${r.date === state.date ? 'comparison-selected' : ''}"><td><button class="row-link" data-date="${r.date}">${E(fullDate(r.date))}</button>${r.holiday ? `<span class="holiday-label">${E(r.holiday)}</span>` : ''}<span class="pattern-note">${E(r.pattern)}</span></td><td>${timeHTML(r.first)}</td><td>${timeHTML(r.last)}</td><td>${r.count}</td><td>${gap(r.median)}</td></tr>`).join('') : '<tr><td colspan="5" class="empty">No dates match this filter in the published feed.</td></tr>';
}
async function renderDirectory() {
  const current = request;
  $('directory-heading').textContent = `${routeName(state.route)} · ${fullDate(state.date)}`;
  $('directory-rows').innerHTML = '<tr><td colspan="5" class="empty">Loading stations…</td></tr>';
  try {
    const rows = await api(`/api/stations?${params()}`);
    if (current !== request) return;
    $('directory-rows').innerHTML = rows.sort((a,b) => a.name.localeCompare(b.name)).map(r => `<tr><td><button class="row-link" data-station="${E(r.id)}">${E(r.name)}</button>${!r.count ? `<span class="pattern-note">${r.arrival_only ? 'Arrival only · no boarding' : 'No scheduled rail departures'}</span>` : ''}</td><td>${timeHTML(r.first)}</td><td>${timeHTML(r.last)}</td><td>${r.count}</td><td>${gap(r.median)}</td></tr>`).join('');
  } catch (e) { $('directory-rows').innerHTML = `<tr><td colspan="5" class="empty error">${E(e.message)}</td></tr>`; }
}
function renderAbout() {
  const m = meta.manifest;
  $('about-content').innerHTML = `<div class="about-grid"><article class="panel about-card"><span class="eyebrow">START HERE, EXPORT WHEN READY</span><h3>The explorer first. Excel alongside.</h3><p>This tool reads the validated CSV data generated with the workbook. The spreadsheet is an export for sharing, auditing, and your own calculations—not the database powering an app.</p><p>Use the timeline to understand a day, compare dates to spot exceptions, and export a selected timetable when you need it.</p><a href="/download/workbook" class="button secondary">↓ Download the complete workbook</a></article><article class="panel about-card"><span class="eyebrow">WHAT THE NUMBERS MEAN</span><h3>Scheduled does not mean guaranteed.</h3><p>These are scheduled estimates from an official MBTA feed. All rail stop times in this snapshot have <code>timepoint=0</code>. This explorer is not connected to live predictions.</p><p>The typical gap is a median across matching departures, not your wait. Your wait depends on your platform-arrival time, direction, and destination. Walking and transfer time are not added automatically.</p></article><article class="panel about-card"><span class="eyebrow">DATES & LATE NIGHTS</span><h3>One service day can span two dates.</h3><p>Times after midnight retain their service-day identity. <strong>25:15:00</strong> means 1:15 AM after the selected date. A <strong>+1 day</strong> badge makes that visible.</p><p>Holiday exceptions are applied per date and route. Christmas and New Year dates fall outside this snapshot; selecting an uncovered date produces no invented schedule.</p><p>Raw service times stay available in CSV exports. All displayed local times are for America/New_York; the service-day convention handles the November DST change.</p></article><article class="panel about-card"><span class="eyebrow">THE SCOPE</span><h3>125 stations. Eight rail routes.</h3><p>Red, Mattapan, Orange, Blue, and Green B/C/D/E. Silver Line and replacement buses are excluded. Parent stations are grouped for discovery; platform IDs are retained in every departure.</p><p>“No departures” can mean no rail service, a terminating direction with arrivals only, or no train to a selected destination. First/last trains are boarding opportunities, not station-door opening hours.</p></article><article class="panel about-card wide"><span class="eyebrow">TRACEABLE TO THE SOURCE</span><h3>Official data, with a paper trail.</h3><p><strong>Feed:</strong> ${E(m.feed_info.feed_version)}<br><strong>Coverage:</strong> ${E(meta.dates[0])} through ${E(meta.dates.at(-1))}<br><strong>Snapshot generated:</strong> ${E(m.generated_utc)}<br><strong>Source SHA-256:</strong> <code>${E(m.sha256)}</code><br><strong>Indexed stop calls:</strong> ${m.sheet_rows.Departures.toLocaleString()} · <strong>Daily station rows:</strong> ${m.sheet_rows['Station hours'].toLocaleString()}</p><p><a href="https://www.mbta.com/developers/gtfs" target="_blank" rel="noreferrer">Official GTFS source ↗</a> &nbsp; <a href="https://www.mbta.com/holidays" target="_blank" rel="noreferrer">Holiday announcements ↗</a> &nbsp; <a href="https://www.mbta.com/alerts" target="_blank" rel="noreferrer">Check current service alerts ↗</a></p><p>The loaded data stays fixed until you rebuild the schedule and restart this server. An absent prediction is not evidence that there are no trains; live predictions are a separate future integration.</p></article></div>`;
}
function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab').forEach(b => { b.classList.toggle('active',b.dataset.tab === tab); b.setAttribute('aria-selected',String(b.dataset.tab === tab)); });
  document.querySelectorAll('.view').forEach(v => v.hidden = v.id !== `view-${tab}`);
  if (tab === 'stations') renderDirectory();
}
document.addEventListener('click', e => {
  const route = e.target.closest('[data-route]'); if (route) return setRoute(route.dataset.route);
  const station = e.target.closest('[data-station]'); if (station) { state.station = station.dataset.station; state.destination = ''; switchTab('timeline'); return refresh(); }
  const day = e.target.closest('[data-date]'); if (day) { state.date = day.dataset.date; if (activeTab === 'compare') switchTab('timeline'); return refresh(); }
  const hour = e.target.closest('[data-hour]'); if (hour) { selectedHour = selectedHour === +hour.dataset.hour ? null : +hour.dataset.hour; shown = 40; renderHistogram(); }
  const tab = e.target.closest('[data-tab]'); if (tab) switchTab(tab.dataset.tab);
});
$('station-search').addEventListener('input',renderStationList);
$('service-date').addEventListener('change', e => { if (e.target.value) { state.date = e.target.value; refresh(); } });
$('direction').addEventListener('change',e => { state.direction = e.target.value; state.destination = ''; refresh(); });
$('destination').addEventListener('change',e => { state.destination = e.target.value; refresh(); });
$('compare-filter').addEventListener('change',renderComparisons);
$('calculate-wait').addEventListener('click',renderWait);
$('ready-time').addEventListener('keydown',e => { if (e.key === 'Enter') renderWait(); });
$('clear-hour').addEventListener('click',() => { selectedHour = null; shown = 40; renderHistogram(); });
$('show-more').addEventListener('click',() => { shown += 80; renderDepartures(); });
for (const [id,delta] of [['previous-date',-1],['next-date',1]]) $(id).addEventListener('click',() => {
  const d = new Date(`${state.date}T12:00:00Z`); d.setUTCDate(d.getUTCDate()+delta); state.date = d.toISOString().slice(0,10); refresh();
});
$('share').addEventListener('click',async () => {
  try { await navigator.clipboard.writeText(location.href); $('share').textContent = '✓ Link copied'; setTimeout(() => $('share').textContent = '↗ Copy view link',1800); }
  catch { $('share').textContent = 'Copy the URL from your address bar'; }
});
$('export').addEventListener('click',() => {
  const rows = [['service_date','route','station_id','direction_id','destination','arrival_service_time','departure_service_time','platform_stop_id','trip_id','stop_sequence','timepoint'], ...boardable().filter(e => selectedHour == null || Math.floor(e.seconds/3600) === selectedHour).map(e => [state.date,state.route,state.station,state.direction,e.destination,e.arrival,e.time,e.platform,e.trip,e.sequence,e.timepoint])];
  const csv = rows.map(r => r.map(c => `"${String(c).replaceAll('"','""')}"`).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  const a = document.createElement('a'); a.href = url; a.download = `${state.route}-${state.station}-${state.date}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
});
async function init() {
  try {
    meta = await api('/api/meta');
    const q = new URLSearchParams(location.search);
    const today = new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York'}).format(new Date());
    const route = meta.routes.some(r => r.id === q.get('route')) ? q.get('route') : 'Red';
    const station = meta.stations.find(s => s.id === q.get('station') && s.routes.includes(route))?.id || (route === 'Red' ? 'place-pktrm' : meta.stations.find(s => s.routes.includes(route)).id);
    state = {date:/^\d{4}-\d{2}-\d{2}$/.test(q.get('date') || '') ? q.get('date') : meta.dates.includes(today) ? today : meta.dates[0],route,station,direction:q.get('direction') === '1' ? '1' : '0',destination:q.get('destination') || ''};
    $('coverage-dates').textContent = `${shortDate(meta.dates[0])} – ${shortDate(meta.dates.at(-1))}, ${meta.dates[0].slice(0,4)}`;
    await refresh();
  } catch(e) { $('load-state').textContent = `${e.message} From the repository root, start the server with python3 -m utilities.schedule_explorer.explore.`; }
}
init();
