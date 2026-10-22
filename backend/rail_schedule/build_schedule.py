#!/usr/bin/env python3
"""Build an auditable MBTA core-rail workbook from an official GTFS snapshot."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import xlsxwriter

if __package__:
    from .paths import ROOT
else:
    from paths import ROOT

FEED_URL = 'https://cdn.mbta.com/MBTA_GTFS.zip'
API = 'https://api-v3.mbta.com'
ROUTES = ('Red', 'Mattapan', 'Orange', 'Blue', 'Green-B', 'Green-C', 'Green-D', 'Green-E')
TZ = ZoneInfo('America/New_York')
DAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')


def fetch(url):
    headers = {'User-Agent': 'MBTA-rail-scheduling-workbook/1.0'}
    if url.startswith(API) and os.getenv('MBTA_API_KEY'):
        headers['x-api-key'] = os.environ['MBTA_API_KEY']
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
            time.sleep(max(4 * (attempt + 1), float(e.headers.get('Retry-After', '0'))))


def sec(value):
    if not value:
        return None
    h, m, s = map(int, value.split(':'))
    return h * 3600 + m * 60 + s


def clock(value):
    if value is None:
        return ''
    return f'{value // 3600:02d}:{value % 3600 // 60:02d}:{value % 60:02d}'


def parse_date(value):
    return datetime.strptime(value, '%Y%m%d').date()


def instant(day, seconds):
    # GTFS specifies noon minus 12 hours as the service-time origin, including DST days.
    noon = datetime.combine(day, datetime.min.time().replace(hour=12), TZ)
    return datetime.fromtimestamp(noon.timestamp() - 43200 + seconds, TZ)


class Feed:
    def __init__(self, path):
        self.path = path
        self.z = zipfile.ZipFile(path)
        self.info = next(self.rows('feed_info.txt'))
        self.start = parse_date(self.info['feed_start_date'])
        self.end = parse_date(self.info['feed_end_date'])
        self.dates = [self.start + timedelta(days=i) for i in range((self.end-self.start).days+1)]
        all_routes = {r['route_id']: r for r in self.rows('routes.txt')}
        self.routes = {rid: r for rid, r in all_routes.items() if rid in ROUTES}
        assert set(self.routes) == set(ROUTES), 'Missing requested rail routes'
        self.stops = {r['stop_id']: r for r in self.rows('stops.txt')}
        all_trips = {r['trip_id']: r for r in self.rows('trips.txt')}
        self.trips = {tid: r for tid, r in all_trips.items() if r['route_id'] in ROUTES and (r.get('trip_route_type') or all_routes[r['route_id']]['route_type']) in ('0', '1')}
        self.service_routes = defaultdict(set)
        for t in self.trips.values():
            self.service_routes[t['service_id']].add(t['route_id'])
        self.cal = {r['service_id']: r for r in self.rows('calendar.txt')}
        self.attrs = {r['service_id']: r for r in self.rows('calendar_attributes.txt')}
        self.exceptions = list(self.rows('calendar_dates.txt'))
        self.overrides = {(r['service_id'], parse_date(r['date'])): r['exception_type'] for r in self.exceptions}
        self.holidays = defaultdict(set)
        for r in self.exceptions:
            if r.get('holiday_name'):
                self.holidays[parse_date(r['date'])].add(r['holiday_name'])
        self.directions = {(r['route_id'], r['direction_id']): r['direction'] for r in self.rows('directions.txt')}
        self.events = defaultdict(list)
        self.station_routes = defaultdict(set)
        self.skipped_blanks = 0
        for r in self.rows('stop_times.txt'):
            trip = self.trips.get(r['trip_id'])
            if not trip:
                continue
            arr, dep = sec(r['arrival_time']), sec(r['departure_time'])
            if arr is None or dep is None:
                self.skipped_blanks += 1
                continue
            stop = self.stops[r['stop_id']]
            station = stop.get('parent_station') or r['stop_id']
            self.station_routes[station].add(trip['route_id'])
            self.events[(trip['route_id'], trip['service_id'])].append({
                'station': station, 'stop': r['stop_id'], 'trip': r['trip_id'],
                'direction': trip['direction_id'], 'destination': r['stop_headsign'] or trip['trip_headsign'],
                'arrival': arr, 'departure': dep, 'pickup': r['pickup_type'] or '0',
                'dropoff': r['drop_off_type'] or '0', 'timepoint': r['timepoint'] or '1',
                'sequence': int(r['stop_sequence']), 'service': trip['service_id'],
            })
        # Do not silently treat frequency-based service or multi-route rail trips as fixed departures.
        if 'frequencies.txt' in self.z.namelist():
            assert not any(r['trip_id'] in self.trips for r in self.rows('frequencies.txt')), 'Rail frequencies require expansion'
        self.excluded_shuttle_trips = set()
        if 'multi_route_trips.txt' in self.z.namelist():
            for r in self.rows('multi_route_trips.txt'):
                if r['added_route_id'] in ROUTES:
                    trip = all_trips[r['trip_id']]
                    mode = trip.get('trip_route_type') or all_routes[trip['route_id']]['route_type']
                    if mode not in ('0', '1'):
                        self.excluded_shuttle_trips.add(r['trip_id'])
                    else:
                        raise ValueError('Multi-route rail trips need expansion before rebuilding')
        assert self.skipped_blanks == 0, 'Missing rail stop times; refuse incomplete output'
        assert all(e['pickup'] in ('0', '1') and e['dropoff'] in ('0', '1') for es in self.events.values() for e in es), 'Conditional boarding needs explicit handling'
        self.profiles = {}
        self.profile_dates = defaultdict(list)
        self.calendar = []
        for day in self.dates:
            active = self.active(day)
            for route in ROUTES:
                services = tuple(sorted(s for s in active if route in self.service_routes[s]))
                key = (route, services)
                if key not in self.profiles:
                    self.profiles[key] = len(self.profiles) + 1
                pid = self.profiles[key]
                self.profile_dates[pid].append(day)
                changes = [r for r in self.exceptions if parse_date(r['date']) == day and route in self.service_routes.get(r['service_id'], set())]
                labels = sorted({self.attrs.get(s, {}).get('service_description', s) for s in services})
                self.calendar.append([day.isoformat(), day.strftime('%A'), '; '.join(sorted(self.holidays[day])),
                                      route, pid, 'Published rail service' if services else 'No scheduled rail service',
                                      '; '.join(labels), '; '.join(services),
                                      sum(r['exception_type'] == '1' for r in changes),
                                      sum(r['exception_type'] == '2' for r in changes)])
        self.profile_events = {}
        for (route, services), pid in self.profiles.items():
            self.profile_events[pid] = sorted([e for s in services for e in self.events[(route, s)]],
                                             key=lambda e: (e['station'], e['direction'], e['departure'], e['trip'], e['sequence']))

    def rows(self, name):
        with self.z.open(name) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig'))

    def active(self, day):
        result = {s for s, r in self.cal.items() if parse_date(r['start_date']) <= day <= parse_date(r['end_date']) and r[DAYS[day.weekday()]] == '1'}
        for (s, d), kind in self.overrides.items():
            if d == day:
                if kind == '1':
                    result.add(s)
                else:
                    result.discard(s)
        return result


def metrics(events):
    departures = sorted(e['departure'] for e in events if e['pickup'] == '0')
    gaps = [b-a for a, b in zip(departures, departures[1:])]
    return [clock(min((e['arrival'] for e in events), default=None)),
            clock(max((e['arrival'] for e in events), default=None)),
            clock(departures[0]) if departures else '', clock(departures[-1]) if departures else '',
            len(departures), round(min(gaps)/60, 3) if gaps else None,
            round(statistics.median(gaps)/60, 3) if gaps else None,
            round(max(gaps)/60, 3) if gaps else None,
            '; '.join(sorted({e['destination'] for e in events if e['pickup'] == '0'}))]


class Output:
    def __init__(self, path):
        path.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.wb = xlsxwriter.Workbook(path / 'MBTA_Rail_Scheduling.xlsx', {'constant_memory': True, 'strings_to_urls': False})
        self.wb.set_properties({'title': 'MBTA core rail scheduling', 'author': 'Official MBTA GTFS; compiled scheduling workbook'})
        self.header = self.wb.add_format({'bold': True, 'bg_color': '#16324F', 'font_color': 'white', 'text_wrap': True, 'valign': 'vcenter'})
        self.input = self.wb.add_format({'bg_color': '#FFF2CC', 'border': 1})
        self.wrap = self.wb.add_format({'text_wrap': True, 'valign': 'top'})
        self.counts = {}

    def table(self, name, headers, rows):
        ws = self.wb.add_worksheet(name)
        ws.freeze_panes(1, 0)
        ws.set_row(0, 34)
        ws.write_row(0, 0, headers, self.header)
        ws.set_column(0, len(headers)-1, 19)
        for i, h in enumerate(headers):
            if any(x in h.lower() for x in ('station name', 'destination', 'description', 'detail', 'header', 'url', 'service ids')):
                ws.set_column(i, i, 40)
        n = 0
        with gzip.open(self.path / (name.lower().replace(' ', '_') + '.csv.gz'), 'wt', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for n, row in enumerate(rows, 1):
                if n >= 1048576:
                    raise ValueError(f'{name} exceeds Excel row limit')
                ws.write_row(n, 0, row)
                writer.writerow(row)
        ws.autofilter(0, 0, n, len(headers)-1)
        self.counts[name] = n
        return ws


def build(feed, out):
    f = feed
    generated = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(f.path.read_bytes()).hexdigest()
    archive = ROOT / 'data' / 'raw' / f'MBTA_GTFS_{digest[:16]}.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        archive.write_bytes(f.path.read_bytes())
    o = Output(out)
    note_rows = [
        ['Scope', 'Red, Mattapan, Orange, Blue, Green B/C/D/E; rail only.'],
        ['Coverage', f'{f.start} through {f.end}, inclusive. Dates outside this feed have no published times in this workbook.'],
        ['Data version', f.info['feed_version']], ['Generated UTC', generated],
        ['Source ZIP', FEED_URL], ['Snapshot SHA256', digest],
        ['Pinned local ZIP', str(archive.relative_to(ROOT))],
        ['Start here', 'Station hours: filter service date, route, station, direction for first/last scheduled arrival and boarding.'],
        ['All trip times', 'Service calendar maps each date + route to a numeric profile. Departures contains every stop event for each profile, including arrival-only terminal calls.'],
        ['Wait lookup', 'Yellow cells accept date, route, station ID, direction, optional exact destination, and passenger platform-arrival service time. Excel 2019+/365 MINIFS support required.'],
        ['Time format', 'Service HH:MM:SS, not an Excel time-of-day. 25:10:00 is 1:10 AM after the service date. Preserve hours over 24.'],
        ['Scheduled estimates', 'All rail times in this snapshot have timepoint=0 (estimated/non-timepoint). Scheduled seconds and gaps are not guaranteed operating times.'],
        ['First / last', 'Arrival columns describe stop calls; boarding columns only pickup_type=0. Terminal arrivals cannot be used as boarding departures. These are not station-door opening hours.'],
        ['Direction / destination', 'Direction IDs come from directions.txt. Destination hours preserves headsigns, including short turns. Combined route gaps can count trains that do not reach your destination.'],
        ['Gap definition', 'Gap is next scheduled boardable departure minus previous departure within the same profile/station/route/direction. Destination gap also matches headsign. No overnight gap is included.'],
        ['Actual wait', 'A passenger wait is next usable departure minus platform-arrival time. Actual future wait is unknown; use /predictions with /alerts for an updated estimate.'],
        ['No service', 'No stop calls = no scheduled rail for that station/direction/profile. Arrival only = trains terminate there but cannot be boarded in that direction. Replacement buses are excluded.'],
        ['Holiday handling', 'Use calendar.txt plus additions/removals in calendar_dates.txt; no blanket weekend substitution. Holiday names come from the feed, even when core rail has no exceptions.'],
        ['Holiday publication', 'As retrieved, MBTA holidays page says Thanksgiving and December/January details are forthcoming. Feed times for covered dates exist now and may be revised.'],
        ['Outside coverage', 'Christmas Eve/Day, New Year\'s Eve/Day and later holidays require a later feed. Holidays sheet flags these explicitly.'],
        ['DST', 'Raw GTFS times are preserved. For actual timestamps use America/New_York and GTFS noon-minus-12-hours origin; schedule_lookup.py implements this on DST transition dates.'],
        ['Alerts snapshot', 'Alerts sheet is a dated snapshot, not a live connection. Read active-period boundaries; expired/future notices may be present.'],
        ['Refresh', 'Run python3 -m backend.rail_schedule.build_schedule from the repository root with a fresh GTFS ZIP; refresh predictions independently. See backend/rail_schedule/PLAN.md.'],
    ]
    ws = o.table('Read me', ['Topic', 'Details'], note_rows)
    ws.set_column(0, 0, 25)
    ws.set_column(1, 1, 115, o.wrap)
    for i in range(1, len(note_rows)+1):
        ws.set_row(i, 46)
    o.table('Service calendar', ['Service date', 'Day', 'Holiday name', 'Route', 'Profile ID', 'Coverage status', 'Service description', 'Active service IDs', 'Exceptions added', 'Exceptions removed'], f.calendar)
    summaries = {}
    dest_rows = []
    route_station_dirs = defaultdict(set)
    for (route, service), events in f.events.items():
        for e in events:
            route_station_dirs[route].add((e['station'], e['direction']))
    profile_rows = []
    for (route, services), pid in f.profiles.items():
        groups = defaultdict(list)
        destinations = defaultdict(list)
        events = f.profile_events[pid]
        for e in events:
            groups[(e['station'], e['direction'])].append(e)
            destinations[(e['station'], e['direction'], e['destination'])].append(e)
            route_station_dirs[route].add((e['station'], e['direction']))
        summaries[pid] = {key: metrics(es) for key, es in groups.items()}
        for (station, direction, dest), es in sorted(destinations.items()):
            m = metrics(es)
            dest_rows.append([pid, route, station, f.stops[station]['stop_name'], direction,
                              f.directions.get((route, direction), direction), dest] + m[:8])
        dates = f.profile_dates[pid]
        profile_rows.append([pid, route, min(dates).isoformat(), max(dates).isoformat(), len(dates),
                             len(events), sum(e['pickup'] == '0' for e in events), '; '.join(services)])
    o.table('Profiles', ['Profile ID', 'Route', 'First applicable date', 'Last applicable date', 'Applicable date count', 'Stop calls', 'Boardable calls', 'Active service IDs'], profile_rows)
    metric_headers = ['First arrival service time', 'Last arrival service time', 'First boarding service time', 'Last boarding service time', 'Boardable departures', 'Min gap minutes', 'Median gap minutes', 'Max gap minutes']

    def daily_rows():
        for cal in f.calendar:
            day, weekday, holiday, route, pid = cal[:5]
            for station, direction in sorted(route_station_dirs[route]):
                m = summaries[pid].get((station, direction))
                status = 'No scheduled rail' if m is None else ('Arrival only / no boarding' if m[4] == 0 else 'Scheduled rail')
                yield [day, weekday, holiday, route, station, f.stops[station]['stop_name'], direction,
                       f.directions.get((route, direction), direction), pid, status] + (m or ['', '', '', '', 0, None, None, None, ''])
    o.table('Station hours', ['Service date', 'Day', 'Holiday name', 'Route', 'Station ID', 'Station name', 'Direction ID', 'Direction', 'Profile ID', 'Status'] + metric_headers + ['Boarding destinations'], daily_rows())
    o.table('Destination hours', ['Profile ID', 'Route', 'Station ID', 'Station name', 'Direction ID', 'Direction', 'Destination'] + metric_headers, dest_rows)

    def departure_rows():
        for (route, services), pid in f.profiles.items():
            previous = {}
            previous_dest = {}
            for e in f.profile_events[pid]:
                k = e['station'], e['direction']
                kd = k + (e['destination'],)
                gap = (e['departure'] - previous[k]) if e['pickup'] == '0' and k in previous else None
                dest_gap = (e['departure'] - previous_dest[kd]) if e['pickup'] == '0' and kd in previous_dest else None
                if e['pickup'] == '0':
                    previous[k] = previous_dest[kd] = e['departure']
                yield [pid, route, e['station'], f.stops[e['station']]['stop_name'], e['direction'],
                       e['destination'], clock(e['arrival']), clock(e['departure']), e['departure'],
                       int(e['pickup'] == '0'), int(e['dropoff'] == '0'), gap, dest_gap,
                       e['timepoint'], e['stop'], e['trip'], e['sequence'], e['service']]
    o.table('Departures', ['Profile ID', 'Route', 'Station ID', 'Station name', 'Direction ID', 'Destination',
                           'Arrival service time', 'Departure service time', 'Departure service seconds', 'Can board',
                           'Can alight', 'Gap route seconds', 'Gap destination seconds', 'Timepoint', 'Platform stop ID',
                           'Trip ID', 'Stop sequence', 'Service ID'], departure_rows())
    o.table('Stations', ['Station ID', 'Station name', 'Rail routes', 'Latitude', 'Longitude', 'Wheelchair boarding code'],
            ([s, f.stops[s]['stop_name'], ', '.join(sorted(routes)), f.stops[s]['stop_lat'], f.stops[s]['stop_lon'], f.stops[s]['wheelchair_boarding']] for s, routes in sorted(f.station_routes.items())))
    rail_exceptions = [r for r in f.exceptions if r['service_id'] in f.service_routes]
    o.table('Calendar exceptions', ['Service date', 'Holiday name', 'Service ID', 'Rail routes', 'Exception type', 'Meaning'],
            ([parse_date(r['date']).isoformat(), r.get('holiday_name', ''), r['service_id'], ', '.join(sorted(f.service_routes[r['service_id']])), r['exception_type'], 'Add service' if r['exception_type'] == '1' else 'Remove service'] for r in rail_exceptions))
    holiday_rows = []
    holiday_dates = dict((d, '; '.join(sorted(names))) for d, names in f.holidays.items() if names)
    # Publication watch-list: labels, not inferred timetables or assertions about modified service.
    watch = {'2026-12-24': 'Christmas Eve', '2026-12-25': 'Christmas Day', '2026-12-31': "New Year's Eve", '2027-01-01': "New Year's Day"}
    for d, name in watch.items():
        holiday_dates.setdefault(date.fromisoformat(d), name)
    for day, name in sorted(holiday_dates.items()):
        for route in ROUTES:
            row = next((r for r in f.calendar if r[0] == day.isoformat() and r[3] == route), None)
            holiday_rows.append([day.isoformat(), day.strftime('%A'), name, route, row[4] if row else None,
                                 'Published in feed; subject to update' if row else 'Outside feed; times not published here',
                                 row[6] if row else '', row[8] if row else None, row[9] if row else None,
                                 'https://www.mbta.com/holidays'])
    o.table('Holidays', ['Service date', 'Day', 'Holiday name', 'Route', 'Profile ID', 'Publication status', 'Service description', 'Exceptions added', 'Exceptions removed', 'Official holiday URL'], holiday_rows)

    alerts_status = 'ok'
    try:
        alert_url = API + '/alerts?' + urllib.parse.urlencode({'filter[route]': ','.join(ROUTES), 'page[limit]': 100})
        alerts = []
        while alert_url:
            payload = json.loads(fetch(alert_url))
            alerts.extend(payload['data'])
            alert_url = payload.get('links', {}).get('next')
            if alert_url:
                alert_url = urllib.parse.urljoin(API, alert_url)
                time.sleep(3.1)
        alerts_retrieved = datetime.now(timezone.utc).isoformat()
        (out / 'alerts_snapshot.json').write_text(json.dumps({'retrieved_utc': alerts_retrieved, 'data': alerts}, indent=2))
    except Exception as exc:
        alerts_status = str(exc)
        alerts = []
    o.table('Alerts snapshot', ['Retrieved UTC', 'Alert ID', 'Effect', 'Severity', 'Header', 'Description', 'Active periods JSON', 'Informed entities JSON', 'URL'],
            ([alerts_retrieved, a['id'], a['attributes'].get('effect'), a['attributes'].get('severity'), a['attributes'].get('header'), a['attributes'].get('description'), json.dumps(a['attributes'].get('active_period')), json.dumps(a['attributes'].get('informed_entity')), a['attributes'].get('url')] for a in alerts))
    if alerts_status != 'ok':
        raise RuntimeError('Alerts fetch failed; rebuild before distributing: ' + alerts_status)

    ws = o.wb.add_worksheet('Wait lookup')
    ws.set_column('A:A', 33)
    ws.set_column('B:B', 38)
    ws.set_column('C:C', 110)
    ws.write_row(0, 0, ['Input / result', 'Value', 'How to use'], o.header)
    sample_day = max(f.start, min(datetime.now(TZ).date(), f.end)).isoformat()
    inputs = [('Service date', sample_day, 'YYYY-MM-DD; choose a covered service date.'),
              ('Route', 'Red', ', '.join(ROUTES)), ('Station ID', 'place-pktrm', 'Look up IDs on Stations.'),
              ('Direction ID', 0, '0 or 1; direction names depend on route.'),
              ('Destination (optional)', 'Ashmont', 'Exact headsign from Destination hours; blank = any destination on chosen route/direction.'),
              ('Platform arrival service time', '08:00:00', 'HH:MM:SS as text, including 24+ hours after midnight.')]
    for i, (label, value, help_text) in enumerate(inputs, 1):
        ws.write(i, 0, label)
        ws.write(i, 1, value, o.input)
        ws.write(i, 2, help_text)
    cn = o.counts['Service calendar'] + 1
    dn = o.counts['Departures'] + 1
    cr = lambda c: f"'Service calendar'!${c}$2:${c}${cn}"
    dr = lambda c: f"Departures!${c}$2:${c}${dn}"
    pid = next(r[4] for r in f.calendar if r[0] == sample_day and r[3] == 'Red')
    choices = [e['departure'] for e in f.profile_events[pid] if e['station'] == 'place-pktrm' and e['direction'] == '0' and e['pickup'] == '0' and e['destination'] == 'Ashmont' and e['departure'] >= 28800]
    next_dep = min(choices) if choices else 0
    formulas = [
        ('Resolved profile ID', f'=SUMIFS({cr("E")},{cr("A")},B2,{cr("D")},B3)', pid),
        ('Arrival service seconds', '=IFERROR(VALUE(LEFT(B7,FIND(":",B7)-1))*3600+VALUE(MID(B7,FIND(":",B7)+1,2))*60+VALUE(RIGHT(B7,2)),"")', 28800),
        ('Next departure seconds', f'=IF(OR(B9=0,B10=""),0,IF(B6="",_xlfn.MINIFS({dr("I")},{dr("A")},B9,{dr("C")},B4,{dr("E")},B5,{dr("J")},1,{dr("I")},">="&B10),_xlfn.MINIFS({dr("I")},{dr("A")},B9,{dr("C")},B4,{dr("E")},B5,{dr("J")},1,{dr("I")},">="&B10,{dr("F")},B6)))', next_dep),
        ('Next scheduled departure', '=IF(B9=0,"Date / route outside coverage",IF(B11=0,"No more matching departures",TEXT(INT(B11/3600),"00")&":"&TEXT(MOD(INT(B11/60),60),"00")&":"&TEXT(MOD(B11,60),"00")))', clock(next_dep) if next_dep else 'No more matching departures'),
        ('Scheduled wait minutes', '=IF(OR(B11=0,B10=""),"",(B11-B10)/60)', (next_dep-28800)/60 if next_dep else ''),
    ]
    for i, (label, formula, cached) in enumerate(formulas, 8):
        ws.write(i, 0, label)
        ws.write_formula(i, 1, formula, None, cached)
    ws.write(15, 0, 'Scope of lookup')
    ws.write(15, 2, 'Selected service day only. No rollover to the next service day; no result means no further matching departure in that profile.')
    ws.write(16, 0, 'Scheduled estimate')
    ws.write(16, 2, 'This is not live. It assumes you are already at the platform. Add your own walking / transfer buffer before entering arrival time.')
    ws.data_validation('B3', {'validate': 'list', 'source': list(ROUTES)})
    ws.data_validation('B5', {'validate': 'integer', 'criteria': 'between', 'minimum': 0, 'maximum': 1})
    o.wb.close()
    manifest = {'generated_utc': generated, 'source_url': FEED_URL, 'sha256': digest, 'feed_info': f.info,
                'local_archive': str(archive.relative_to(ROOT)), 'alerts_retrieved_utc': alerts_retrieved,
                'routes': list(ROUTES), 'station_count': len(f.station_routes), 'profile_count': len(f.profiles),
                'rail_stop_times': sum(map(len, f.events.values())), 'timepoint_counts': dict(Counter(e['timepoint'] for es in f.events.values() for e in es)),
                'sheet_rows': o.counts, 'alerts_status': alerts_status, 'alert_count': len(alerts), 'blank_times': f.skipped_blanks,
                'excluded_multi_route_bus_shuttle_trips': len(f.excluded_shuttle_trips)}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gtfs', type=Path, help='Existing official GTFS ZIP; otherwise download fresh')
    parser.add_argument('--out', type=Path, default=ROOT / 'output')
    args = parser.parse_args()
    path = args.gtfs
    if path is None:
        path = ROOT / 'data' / 'MBTA_GTFS.zip'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch(FEED_URL))
    build(Feed(path), args.out)


if __name__ == '__main__':
    main()
