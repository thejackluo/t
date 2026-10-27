"""Compile scheduled MBTA bus *connectors* from the pinned GTFS snapshot.

Buses are permitted as scheduled public transport between lines but never earn station coverage, so only the
calls that touch an exported rail/Silver station matter: a stop is "adjacent" when GTFS makes it part of the
station (parent_station), publishes a transfer between it and one of the station's platforms, or it lies within
`NEAR_METERS` of the station point. Rail-replacement shuttles and the Silver Line (built separately) are excluded.
The output mirrors the rail tables so the same evaluator loads it; blank bus stop times are skipped, never invented.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from .build_schedule import DAYS, SILVER, clock, parse_date, sec

ROOT = Path(__file__).resolve().parents[2]
NEAR_METERS = 120
REPLACEMENT_DESC = 'Rail Replacement Bus'
DEPARTURE_COLUMNS = ['Profile ID', 'Route', 'Station ID', 'Station name', 'Direction ID', 'Destination',
                     'Arrival service time', 'Departure service time', 'Departure service seconds', 'Can board',
                     'Can alight', 'Gap route seconds', 'Gap destination seconds', 'Timepoint', 'Platform stop ID',
                     'Trip ID', 'Stop sequence', 'Service ID']


def distance(a, b):
    lat = math.radians((a[0] + b[0]) / 2)
    return math.hypot((a[0] - b[0]) * 111320, (a[1] - b[1]) * 111320 * math.cos(lat))


def read_gz(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def write_gz(path, header, rows):
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def build(out):
    out = Path(out)
    manifest = json.loads((out / 'manifest.json').read_text())
    archive = ROOT / manifest['local_archive']
    with archive.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == manifest['sha256'], 'Archive does not match manifest'
    stations = {r['Station ID']: r for r in read_gz(out / 'stations.csv.gz')}
    points = {s: (float(r['Latitude']), float(r['Longitude'])) for s, r in stations.items()}
    calendar_rows = read_gz(out / 'service_calendar.csv.gz')
    calendar_header = list(calendar_rows[0].keys())
    dates = sorted({date.fromisoformat(r['Service date']) for r in calendar_rows})
    holidays = {r['Service date']: r[calendar_header[2]] for r in calendar_rows}
    z = zipfile.ZipFile(archive)

    def rows(name):
        with z.open(name) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''))

    all_routes = {r['route_id']: r for r in rows('routes.txt')}
    routes = {rid: r for rid, r in all_routes.items()
              if r['route_type'] == '3' and r['route_desc'] != REPLACEMENT_DESC and rid not in SILVER and not rid.startswith('Shuttle')}
    stops = {r['stop_id']: r for r in rows('stops.txt')}
    station_of = {}  # platform/child stop -> station
    for s, r in stations.items():
        for stop in (r.get('Stop IDs') or '').split():
            station_of[stop] = s
    for stop_id, r in stops.items():
        if r.get('parent_station') in stations:
            station_of.setdefault(stop_id, r['parent_station'])
    linked = defaultdict(set)
    for r in rows('transfers.txt'):
        a, b = r['from_stop_id'], r['to_stop_id']
        if a in station_of and b not in station_of:
            linked[b].add(station_of[a])
        if b in station_of and a not in station_of:
            linked[a].add(station_of[b])

    adjacency = {}
    def adjacent(stop_id):
        if stop_id in adjacency:
            return adjacency[stop_id]
        r = stops[stop_id]
        point = (float(r['stop_lat']), float(r['stop_lon']))
        result = None
        if stop_id in station_of:
            s = station_of[stop_id]
            result = (s, round(distance(point, points[s])), 'gtfs_parent')
        elif linked.get(stop_id):
            s = min(linked[stop_id], key=lambda s: distance(point, points[s]))
            result = (s, round(distance(point, points[s])), 'gtfs_transfers')
        else:
            s, meters = min(((s, distance(point, p)) for s, p in points.items()), key=lambda x: x[1])
            if meters <= NEAR_METERS:
                result = (s, round(meters), 'proximity')
        adjacency[stop_id] = result
        return result

    trips = {t['trip_id']: t for t in rows('trips.txt')
             if t['route_id'] in routes and (t.get('trip_route_type') or '3') == '3'}
    calls, blanks = defaultdict(list), 0
    for r in rows('stop_times.txt'):
        trip = trips.get(r['trip_id'])
        if not trip:
            continue
        near = adjacent(r['stop_id'])
        if not near:
            continue
        arr, dep = sec(r['arrival_time']), sec(r['departure_time'])
        if arr is None or dep is None:
            blanks += 1
            continue
        calls[r['trip_id']].append({'station': near[0], 'stop': r['stop_id'], 'sequence': int(r['stop_sequence']),
                                    'arrival': arr, 'departure': dep, 'pickup': r['pickup_type'] or '0',
                                    'dropoff': r['drop_off_type'] or '0', 'timepoint': r['timepoint'] or '1',
                                    'headsign': r.get('stop_headsign') or trip['trip_headsign']})
    events, service_routes, used_stops, dropped = defaultdict(list), defaultdict(set), defaultdict(set), 0
    for tid, cs in calls.items():
        if len({c['station'] for c in cs}) < 2:
            dropped += 1
            continue
        trip = trips[tid]
        service_routes[trip['service_id']].add(trip['route_id'])
        for c in cs:
            used_stops[c['stop']].add(trip['route_id'])
            events[(trip['route_id'], trip['service_id'])].append({**c, 'trip': tid, 'direction': trip['direction_id'],
                                                                  'destination': trip['trip_headsign'], 'service': trip['service_id']})
    cal = {r['service_id']: r for r in rows('calendar.txt')}
    attrs = {r['service_id']: r for r in rows('calendar_attributes.txt')}
    exceptions = list(rows('calendar_dates.txt'))
    overrides = {(r['service_id'], parse_date(r['date'])): r['exception_type'] for r in exceptions}

    def active(day):
        result = {s for s, r in cal.items() if parse_date(r['start_date']) <= day <= parse_date(r['end_date']) and r[DAYS[day.weekday()]] == '1'}
        for (s, d), kind in overrides.items():
            if d == day:
                (result.add if kind == '1' else result.discard)(s)
        return result

    profiles, calendar, bus_routes = {}, [], sorted(r for r in routes if any(r in rs for rs in service_routes.values()))
    for day in dates:
        today = active(day)
        for route in bus_routes:
            services = tuple(sorted(s for s in today if route in service_routes[s]))
            key = (route, services)
            if key not in profiles:
                profiles[key] = 100000 + len(profiles) + 1
            labels = sorted({attrs.get(s, {}).get('service_description', s) for s in services})
            changes = [r for r in exceptions if parse_date(r['date']) == day and route in service_routes.get(r['service_id'], set())]
            calendar.append([day.isoformat(), day.strftime('%A'), holidays.get(day.isoformat(), ''), route, profiles[key],
                             'Published bus service' if services else 'No scheduled bus service', '; '.join(labels), '; '.join(services),
                             sum(r['exception_type'] == '1' for r in changes), sum(r['exception_type'] == '2' for r in changes)])

    def departure_rows():
        for (route, services), pid in profiles.items():
            es = sorted((e for s in services for e in events[(route, s)]), key=lambda e: (e['station'], e['direction'], e['departure'], e['trip'], e['sequence']))
            for e in es:
                yield [pid, route, e['station'], stations[e['station']]['Station name'], e['direction'], e['destination'],
                       clock(e['arrival']), clock(e['departure']), e['departure'], int(e['pickup'] == '0'), int(e['dropoff'] == '0'),
                       None, None, e['timepoint'], e['stop'], e['trip'], e['sequence'], e['service']]

    write_gz(out / 'bus_calendar.csv.gz', calendar_header, calendar)
    count = 0
    def counted():
        nonlocal count
        for row in departure_rows():
            count += 1
            yield row
    write_gz(out / 'bus_departures.csv.gz', DEPARTURE_COLUMNS, counted())
    write_gz(out / 'bus_stops.csv.gz', ['Stop ID', 'Stop name', 'Station ID', 'Meters', 'Source', 'Routes'],
             ([s, stops[s]['stop_name'], *adjacency[s], ', '.join(sorted(rs))] for s, rs in sorted(used_stops.items())))
    summary = {'sha256': manifest['sha256'], 'routes': {r: {'short_name': routes[r]['route_short_name'] or r, 'long_name': routes[r]['route_long_name'],
                                                            'desc': routes[r]['route_desc'], 'color': '#' + (routes[r]['route_color'] or 'FFC72C')} for r in bus_routes},
               'route_count': len(bus_routes), 'profile_count': len(profiles), 'stop_count': len(used_stops), 'departure_rows': count,
               'near_meters': NEAR_METERS, 'excluded': {'rail_replacement_routes': sum(r['route_desc'] == REPLACEMENT_DESC for r in all_routes.values()),
                                                        'silver_routes': list(SILVER), 'trips_touching_fewer_than_two_stations': dropped,
                                                        'blank_stop_times_skipped': blanks},
               'coverage_rule': 'Bus rides never add stations to rail or Silver coverage.'}
    (out / 'bus_manifest.json').write_text(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', default=ROOT / 'output', help='Directory holding the rail export (manifest.json, stations.csv.gz)')
    args = parser.parse_args()
    summary = build(args.out)
    print(json.dumps({k: v for k, v in summary.items() if k != 'routes'}, indent=2))


if __name__ == '__main__':
    main()
