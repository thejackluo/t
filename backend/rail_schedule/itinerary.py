"""Track geometry and date-specific itinerary evaluation over the pinned rail exports."""
import csv
import gzip
import hashlib
import heapq
import io
import json
import math
import zipfile
from collections import defaultdict
from datetime import date
from itertools import count
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLORS = {'Red': '#DA291C', 'Orange': '#ED8B00', 'Blue': '#003DA5', 'Mattapan': '#9b342c',
          **{f'Green-{b}': '#00843D' for b in 'BCDE'}}


def distance(a, b):
    """Meters, from [latitude, longitude] geographic coordinates."""
    lat = math.radians((a[0] + b[0]) / 2)
    return math.hypot(math.radians(a[0] - b[0]), math.radians(a[1] - b[1]) * math.cos(lat)) * 6371000


def service_seconds(value):
    parts = str(value).split(':')
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise ValueError('Use service HH:MM or HH:MM:SS, including 24+ hours after midnight.')
    h, m = map(int, parts[:2])
    s = int(parts[2]) if len(parts) == 3 else 0
    if not (0 <= h <= 47 and 0 <= m < 60 and 0 <= s < 60):
        raise ValueError('Service time must be between 00:00:00 and 47:59:59.')
    return h * 3600 + m * 60 + s


class RailNetwork:
    def __init__(self, directory=ROOT / 'output', archive=None):
        self.directory = Path(directory)
        self.manifest = json.loads((self.directory / 'manifest.json').read_text())
        archive = Path(archive) if archive else ROOT / self.manifest['local_archive']
        # Geometry must describe exactly the same source as the timetable.
        with archive.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != self.manifest['sha256']:
            raise ValueError('GTFS archive does not match the schedule manifest.')
        self.stations = {r['Station ID']: {'id': r['Station ID'], 'name': r['Station name'],
                         'routes': r['Rail routes'].split(', '),
                         'point': [float(r['Latitude']), float(r['Longitude'])]}
                         for r in self.rows('stations')}
        self.calendar = {(r['Service date'], r['Route']): r for r in self.rows('service_calendar')}
        trips = defaultdict(list)
        for r in self.rows('departures'):
            trips[(r['Profile ID'], r['Trip ID'])].append({
                'station': r['Station ID'], 'stop': r['Platform stop ID'], 'sequence': int(r['Stop sequence']),
                'arrival': service_seconds(r['Arrival service time']), 'departure': int(r['Departure service seconds']),
                'board': r['Can board'] == '1', 'alight': r['Can alight'] == '1', 'timepoint': r['Timepoint'],
                'route': r['Route'], 'direction': r['Direction ID'], 'headsign': r['Destination'],
                'service': r['Service ID']})
        wanted = {t for _, t in trips}
        self.stops, self.trip_meta, shapes = {}, {}, defaultdict(list)
        self.transfer_rules = defaultdict(list)
        self.pathways = defaultdict(list)
        with zipfile.ZipFile(archive) as z:
            def table(name):
                with z.open(name) as raw:
                    yield from csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''))
            self.stops = {r['stop_id']: r for r in table('stops.txt')}
            self.trip_meta = {r['trip_id']: r for r in table('trips.txt') if r['trip_id'] in wanted}
            shape_ids = {r['shape_id'] for r in self.trip_meta.values()}
            for r in table('shapes.txt'):
                if r['shape_id'] in shape_ids:
                    shapes[r['shape_id']].append((int(r['shape_pt_sequence']), [float(r['shape_pt_lat']), float(r['shape_pt_lon'])]))
            for r in table('transfers.txt'):
                self.transfer_rules[(r['from_stop_id'], r['to_stop_id'])].append(r)
            for r in table('pathways.txt'):
                a, b = r['from_stop_id'], r['to_stop_id']
                if self.parent(a) not in self.stations or self.parent(b) not in self.stations:
                    continue
                # Walk time is a sourced estimate; never infer a reverse pathway unless GTFS permits it.
                seconds = float(r['traversal_time'] or 0)
                estimated = not bool(r['traversal_time'])
                if not seconds:
                    length = float(r['length'] or distance(self.stop_point(a), self.stop_point(b)))
                    seconds = length / 1.2  # Explicit provisional indoor walking assumption.
                self.pathways[a].append((b, seconds, estimated))
                if r['is_bidirectional'] == '1':
                    self.pathways[b].append((a, seconds, estimated))
        shapes = {s: [p for _, p in sorted(points)] for s, points in shapes.items()}
        self.patterns, self.scheduled, self.starts = {}, defaultdict(list), defaultdict(list)
        for (profile, trip), calls in trips.items():
            calls.sort(key=lambda c: c['sequence'])
            meta = self.trip_meta[trip]
            key = json.dumps([meta['route_id'], meta['direction_id'], meta['shape_id'],
                              [(c['stop'], c['board'], c['alight']) for c in calls]])
            pid = hashlib.sha256(key.encode()).hexdigest()[:16]
            if pid not in self.patterns:
                shape = shapes[meta['shape_id']]
                positions = self.shape_positions(shape, calls)
                self.patterns[pid] = {'id': pid, 'route': meta['route_id'], 'direction': meta['direction_id'],
                    'shape_id': meta['shape_id'], 'shape': shape, 'positions': positions, 'calls': calls,
                    'headsign': calls[0]['headsign'], 'profiles': set()}
                for i, c in enumerate(calls[:-1]):
                    if c['board']:
                        self.starts[c['station']].append((pid, i))
            self.patterns[pid]['profiles'].add(profile)
            self.scheduled[(profile, pid)].append({'id': trip, 'service': meta['service_id'], 'calls': calls})
        self._path_cache = {}
        self.interchanges = defaultdict(set)
        edges = list(self.transfer_rules) + [(a, b) for a, es in self.pathways.items() for b, _, _ in es]
        for a, b in edges:
            origin, target = self.parent(a), self.parent(b)
            if origin in self.stations and target in self.stations and origin != target:
                self.interchanges[origin].add(target)

    def rows(self, name):
        with gzip.open(self.directory / f'{name}.csv.gz', 'rt', encoding='utf-8', newline='') as f:
            yield from csv.DictReader(f)

    def parent(self, stop):
        r = self.stops.get(stop, {})
        return r.get('parent_station') or stop

    def stop_point(self, stop):
        r = self.stops[stop]
        if not r['stop_lat'] or not r['stop_lon']:
            return self.stations[self.parent(stop)]['point']
        return [float(r['stop_lat']), float(r['stop_lon'])]

    def shape_positions(self, shape, calls):
        """Project platforms onto ordered shape segments, preserving travel direction."""
        positions, lower = [], 0.0
        for c in calls:
            point = self.stop_point(c['stop'])
            best = (float('inf'), lower)
            for j in range(max(0, int(lower)), len(shape) - 1):
                a, b = shape[j], shape[j + 1]
                scale = math.cos(math.radians(point[0]))
                ax, ay = (a[1] - point[1]) * scale, a[0] - point[0]
                dx, dy = (b[1] - a[1]) * scale, b[0] - a[0]
                denom = dx * dx + dy * dy
                fraction = max(0, min(1, -(ax * dx + ay * dy) / denom)) if denom else 0
                if j + fraction < lower:
                    fraction = lower - j
                error = (ax + fraction * dx) ** 2 + (ay + fraction * dy) ** 2
                if error < best[0]:
                    best = (error, j + fraction)
            lower = best[1]
            positions.append(lower)
        return positions

    @staticmethod
    def interpolate(shape, position):
        i = min(int(position), len(shape) - 2)
        t = position - i
        return [round(shape[i][k] + t * (shape[i + 1][k] - shape[i][k]), 6) for k in (0, 1)]

    def ride(self, pid, start, end):
        p = self.patterns[pid]
        if not (0 <= start < end < len(p['calls'])):
            raise ValueError('Invalid ride stop sequence.')
        calls = p['calls'][start:end + 1]
        if not calls[0]['board'] or not calls[-1]['alight']:
            raise ValueError('Boarding or alighting is not allowed at this endpoint.')
        a, b = p['positions'][start], p['positions'][end]
        geometry = [self.interpolate(p['shape'], a)]
        geometry += p['shape'][int(a) + 1:math.ceil(b)]
        geometry.append(self.interpolate(p['shape'], b))
        return {'mode': 'ride', 'pattern': pid, 'start': start, 'end': end, 'route': p['route'],
                'direction': p['direction'], 'headsign': p['headsign'], 'shape_id': p['shape_id'],
                'from': calls[0]['station'], 'to': calls[-1]['station'], 'from_stop': calls[0]['stop'],
                'to_stop': calls[-1]['stop'], 'stations': [c['station'] for c in calls], 'geometry': geometry,
                'geometry_source': 'MBTA GTFS shapes.txt', 'distance': round(sum(distance(x, y) for x, y in zip(geometry, geometry[1:])))}

    def metadata(self):
        seen, lines = set(), []
        for p in self.patterns.values():
            if p['shape_id'] in seen:
                continue
            seen.add(p['shape_id'])
            lines.append({'route': p['route'], 'shape_id': p['shape_id'],
                          'geometry': self.ride(p['id'], 0, len(p['calls']) - 1)['geometry']})
        return {'stations': list(self.stations.values()), 'lines': lines,
                'routes': [{'id': r, 'color': COLORS[r]} for r in self.manifest['routes']],
                'dates': sorted({d for d, _ in self.calendar}), 'manifest': self.manifest,
                'ruleset': 'rail-rehearsal-v1', 'pattern_count': len(self.patterns)}

    def pathway_time(self, origin, destination):
        key = (origin, destination)
        if key in self._path_cache:
            return self._path_cache[key]
        q, visited = [(0, origin, False)], set()
        while q:
            t, stop, estimated = heapq.heappop(q)
            if stop in visited:
                continue
            visited.add(stop)
            if stop == destination:
                self._path_cache[key] = (t, estimated)
                return t, estimated
            for target, cost, assumption in self.pathways[stop]:
                heapq.heappush(q, (t + cost, target, estimated or assumption))
        self._path_cache[key] = None
        return None

    def transfer(self, origin, destination, buffer=0, from_trip=None, to_trip=None):
        """Directed platform constraints; trip-specific GTFS rules remain trip-specific."""
        rules = self.transfer_rules.get((origin, destination), [])
        applicable = [r for r in rules if (not r['from_trip_id'] or r['from_trip_id'] == from_trip)
                      and (not r['to_trip_id'] or r['to_trip_id'] == to_trip)]
        # Prefer the most specific matching rule, as required by GTFS.
        if applicable:
            specificity = max(bool(r['from_trip_id']) + bool(r['to_trip_id']) for r in applicable)
            applicable = [r for r in applicable if bool(r['from_trip_id']) + bool(r['to_trip_id']) == specificity]
        if any(r['transfer_type'] == '3' for r in applicable):
            return None
        path = self.pathway_time(origin, destination)
        if path is None and not applicable:
            return None
        minimum = max([float(r['min_transfer_time'] or 0) for r in applicable] + [0])
        walk = max([float(r['min_walk_time'] or 0) for r in applicable] + [path[0] if path else 0])
        suggested = max([float(r['suggested_buffer_time'] or 0) for r in applicable] + [0])
        return {'seconds': math.ceil(max(minimum, walk + suggested) + buffer),
                'walk_seconds': math.ceil(walk), 'minimum_seconds': minimum, 'buffer_seconds': buffer,
                'source': 'GTFS directed transfers/pathways', 'estimated': path[1] if path else not bool(walk)}

    def options(self, origin, destination, day, route=''):
        date.fromisoformat(day)
        if origin not in self.stations or destination not in self.stations or origin == destination:
            raise ValueError('Choose two different MBTA stations.')
        if route and route not in COLORS:
            raise ValueError('Unknown line filter.')
        if not any(d == day for d, _ in self.calendar):
            return {'options': [], 'message': 'This date is outside the imported timetable. Choose a published service date.'}
        serial = count()
        queue = [(0, next(serial), origin, None, [], frozenset([origin]))]
        best, answers, signatures = defaultdict(list), [], set()
        expansions = 0
        while queue and len(answers) < 3 and expansions < 12000:
            cost, _, station, previous_stop, legs, visited = heapq.heappop(queue)
            expansions += 1
            if station == destination:
                signature = tuple((x['route'], x['from'], x['to'], tuple(x['stations'])) for x in legs)
                if signature not in signatures:
                    answers.append({'legs': legs, 'transfers': len(legs) - 1, 'approx_minutes': round(cost / 60),
                                    'label': ' → '.join(x['route'] for x in legs)})
                    signatures.add(signature)
                continue
            if len(legs) >= 4:
                continue
            state = (station, previous_stop)
            if len(best[state]) >= 3 and cost > best[state][-1]:
                continue
            best[state].append(cost)
            best[state].sort()
            best[state] = best[state][:3]
            candidate_keys = set()
            boarding_stations = [station] + (sorted(self.interchanges[station]) if previous_stop else [])
            for pid, i in (entry for s in boarding_stations for entry in self.starts[s]):
                p = self.patterns[pid]
                if p['calls'][i]['station'] != station and p['calls'][i]['station'] in visited:
                    continue
                if route and p['route'] != route:
                    continue
                cal = self.calendar.get((day, p['route']))
                if not cal or cal['Profile ID'] not in p['profiles']:
                    continue
                if legs and legs[-1]['route'] == p['route']:
                    continue  # A single ride pattern should represent continuous same-line service.
                transfer = self.transfer(previous_stop, p['calls'][i]['stop']) if previous_stop else {'seconds': 0}
                if transfer is None:
                    continue
                for j in range(i + 1, len(p['calls'])):
                    c = p['calls'][j]
                    if not c['alight'] or c['station'] in visited:
                        continue
                    signature = (p['route'], tuple(x['stop'] for x in p['calls'][i:j + 1]))
                    if signature in candidate_keys:
                        continue
                    candidate_keys.add(signature)
                    intermediate = {x['station'] for x in p['calls'][i + 1:j + 1]}
                    if intermediate & visited:
                        continue
                    leg = self.ride(pid, i, j)
                    travel = max(1, c['arrival'] - p['calls'][i]['departure'])
                    # Ranking only: exact feasible trips are evaluated after the user selects a path.
                    penalty = 300 if legs else 0
                    heapq.heappush(queue, (cost + travel + transfer['seconds'] + penalty,
                        next(serial), c['station'], c['stop'], legs + [leg], visited | intermediate | {leg['from']}))
        return {'options': answers, 'message': '' if answers else 'No directed rail path found for these stations/date/line. Try All lines or add an explicit foot link.'}

    def canonical_leg(self, leg):
        if not isinstance(leg, dict):
            raise ValueError('Every segment must be an object.')
        if leg.get('mode') == 'ride':
            if leg.get('pattern') not in self.patterns:
                raise ValueError('Ride pattern belongs to a different dataset; choose a new path.')
            return {**self.ride(leg['pattern'], int(leg['start']), int(leg['end'])), 'id': str(leg.get('id', ''))[:100]}
        if leg.get('mode') not in ('run', 'walk'):
            raise ValueError('Unknown segment mode.')
        if leg.get('from') not in self.stations or leg.get('to') not in self.stations or leg['from'] == leg['to']:
            raise ValueError('Foot links need two different MBTA stations.')
        points = leg.get('geometry', [])
        if not isinstance(points, list) or not 2 <= len(points) <= 2000:
            raise ValueError('Foot geometry needs 2–2000 geographic points.')
        for p in points:
            if not isinstance(p, list) or len(p) != 2 or not all(isinstance(n, (float, int)) and math.isfinite(n) for n in p):
                raise ValueError('Invalid foot coordinates.')
            if not (41.5 <= p[0] <= 43 and -72 <= p[1] <= -70):
                raise ValueError('Foot points must be in the Boston planning region.')
        if distance(points[0], self.stations[leg['from']]['point']) > 250 or distance(points[-1], self.stations[leg['to']]['point']) > 250:
            raise ValueError('Foot path endpoints must stay at the selected stations.')
        source = leg.get('geometry_source', 'user_drawn')
        if source not in ('user_drawn', 'straight_line_sketch', 'google_routes'):
            raise ValueError('Unknown foot geometry source.')
        return {'id': str(leg.get('id', ''))[:100], 'mode': leg['mode'], 'from': leg['from'], 'to': leg['to'],
                'geometry': points, 'geometry_source': source,
                'distance': round(sum(distance(a, b) for a, b in zip(points, points[1:]))), 'stations': []}

    def evaluate(self, scenario):
        if scenario.get('dataset', self.manifest['sha256']) != self.manifest['sha256']:
            raise ValueError('Scenario dataset does not match the loaded source snapshot.')
        if scenario.get('ruleset', 'rail-rehearsal-v1') != 'rail-rehearsal-v1':
            raise ValueError('Scenario ruleset is not supported by this rail rehearsal evaluator.')
        day = str(scenario.get('date', ''))
        date.fromisoformat(day)
        ready = service_seconds(scenario.get('time', '08:00'))
        start_time = ready
        legs = scenario.get('legs', [])
        if not isinstance(legs, list) or len(legs) > 250:
            raise ValueError('A scenario supports up to 250 segments.')
        assumptions = scenario.get('assumptions', {})
        if not isinstance(assumptions, dict):
            raise ValueError('Timing assumptions must be an object.')
        def number(name, default, lo, hi):
            value = float(assumptions.get(name, default))
            if not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(f'Invalid {name} assumption.')
            return value
        run_pace = number('run_pace', 6, 2, 30)
        walk_pace = number('walk_pace', 12, 4, 40)
        buffer = number('buffer', 30, 0, 1800)
        access = number('access', 60, 0, 1800)
        result, covered, events, previous, previous_ride = [], set(), [], None, None
        first_board, last_arrival, reason = None, None, ''
        for index, raw in enumerate(legs):
            leg = self.canonical_leg(raw)
            passage = previous_ride and leg['mode'] == 'ride' and self.transfer(previous_ride['to_stop'], leg['from_stop'])
            if previous and previous['to'] != leg['from'] and not passage:
                reason = f"Segment {index + 1} is disconnected from the preceding endpoint. Reorder or replace it."
            item = {**leg, 'status': 'blocked' if reason else 'ok', 'time_kind': 'estimated' if leg['mode'] != 'ride' else 'scheduled_estimate'}
            if reason:
                item['message'] = reason
                result.append(item)
                previous = leg
                continue
            if leg['mode'] != 'ride':
                seconds = math.ceil(leg['distance'] / 1000 * (run_pace if leg['mode'] == 'run' else walk_pace) * 60)
                # Consecutive foot links do not repeatedly exit/re-enter intermediate stations.
                exit_seconds = access if previous_ride or index == 0 else 0
                next_is_ride = index + 1 < len(legs) and isinstance(legs[index + 1], dict) and legs[index + 1].get('mode') == 'ride'
                entry_seconds = access if next_is_ride else 0
                access_seconds = exit_seconds + entry_seconds
                item.update({'start_time': ready, 'departure': ready, 'arrival': ready + seconds + access_seconds,
                             'travel_seconds': seconds, 'access_seconds': access_seconds,
                             'exit_seconds': exit_seconds, 'entry_seconds': entry_seconds, 'wait_seconds': 0, 'transfer_seconds': 0})
                ready = item['arrival']
                previous_ride = None
                events.append({'mode': leg['mode'], 'seconds': seconds, 'time_kind': 'estimated'})
                if access_seconds:
                    events.append({'mode': 'access', 'seconds': access_seconds, 'time_kind': 'estimated'})
            else:
                p = self.patterns[leg['pattern']]
                cal = self.calendar.get((day, p['route']))
                candidates = []
                for trip in self.scheduled.get((cal['Profile ID'], p['id']), []) if cal else []:
                    a, b = trip['calls'][leg['start']], trip['calls'][leg['end']]
                    continuous = bool(previous_ride and previous_ride['trip_id'] == trip['id'] and previous_ride['to_stop'] == a['stop'])
                    transfer = {'seconds': 0, 'source': 'same train' if continuous else 'platform ready'}
                    if previous_ride and not continuous:
                        transfer = self.transfer(previous_ride['to_stop'], a['stop'], buffer, previous_ride['trip_id'], trip['id'])
                    if transfer is None or a['departure'] < ready + transfer['seconds'] or not a['board'] or not b['alight']:
                        continue
                    candidates.append((b['arrival'], a['departure'], trip['id'], trip, transfer, continuous))
                if not candidates:
                    reason = 'No feasible boardable train on this service day, or no permitted directed platform transfer.' if cal else 'Date is outside published schedule coverage.'
                    item.update({'status': 'unavailable', 'message': reason})
                else:
                    _, dep, _, trip, transfer, continuous = min(candidates, key=lambda c: (c[0], c[1], c[2]))
                    arrival = trip['calls'][leg['end']]['arrival']
                    wait = 0 if continuous else dep - ready - transfer['seconds']
                    travel = arrival - (ready if continuous else dep)
                    item.update({'start_time': ready, 'departure': dep, 'arrival': arrival, 'wait_seconds': wait,
                        'travel_seconds': travel, 'transfer_seconds': transfer['seconds'], 'transfer': transfer,
                        'trip_id': trip['id'], 'service_id': trip['service'], 'profile_id': cal['Profile ID'],
                        'continuous': continuous, 'headsign': trip['calls'][leg['start']]['headsign'],
                        'stop_calls': [{**c} for c in trip['calls'][leg['start']:leg['end'] + 1]]})
                    if transfer['seconds']:
                        events.append({'mode': 'transfer', 'from_stop': previous_ride['to_stop'], 'to_stop': leg['from_stop'],
                                       'from': previous_ride['to'], 'to': leg['from'],
                                       'seconds': transfer['seconds'], 'time_kind': 'estimated', 'source': transfer['source']})
                    if wait:
                        events.append({'mode': 'wait', 'seconds': wait, 'time_kind': 'scheduled_estimate', 'pre_start': first_board is None})
                    events.append({'mode': 'ride', 'trip_id': trip['id'], 'seconds': travel, 'time_kind': 'scheduled_estimate'})
                    first_board = dep if first_board is None else first_board
                    last_arrival = arrival
                    ready = arrival
                    covered.update(leg['stations'])
                    previous_ride = item
            result.append(item)
            previous = leg
        totals = {mode: sum(e['seconds'] for e in events if e['mode'] == mode) for mode in ('ride', 'wait', 'transfer', 'access', 'run', 'walk')}
        return {'legs': result, 'events': events, 'covered': sorted(covered),
                'missing': sorted(set(self.stations) - covered), 'status': 'partial' if reason else 'ok', 'message': reason,
                'summary': {'elapsed': ready - start_time, 'first_board': first_board, 'finish': ready,
                            'record_proxy_seconds': last_arrival - first_board if first_board is not None else None,
                            'foot_meters': sum(l.get('distance', 0) for l in result if l['mode'] != 'ride' and l['status'] == 'ok'), **totals},
                'dataset': self.manifest['sha256'], 'ruleset': 'rail-rehearsal-v1', 'coverage_label': 'Rail rehearsal; Silver Line and approved inventory still required'}
