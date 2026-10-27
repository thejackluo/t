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


def clock(seconds):
    """Service-day HH:MM, keeping 24+ hours after midnight."""
    if seconds is None:
        return '—'
    seconds = int(seconds)
    return f'{seconds // 3600:02d}:{seconds % 3600 // 60:02d}'


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
        self.pathways, self.reverse_pathways = defaultdict(list), defaultdict(list)
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
                self.reverse_pathways[b].append((a, seconds, estimated))
                if r['is_bidirectional'] == '1':
                    self.pathways[b].append((a, seconds, estimated))
                    self.reverse_pathways[a].append((b, seconds, estimated))
        self.entrances = defaultdict(list)
        for stop_id, r in self.stops.items():
            if r['location_type'] == '2' and r['parent_station'] in self.stations:
                self.entrances[r['parent_station']].append(stop_id)
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
        self._path_cache, self._ride_cache, self._last_cache, self._twin_cache = {}, {}, {}, {}
        self.pathway_stations = {self.parent(a) for a in self.pathways} | {self.parent(b) for es in self.pathways.values() for b, _, _ in es}
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

    def geometry(self, p, start, end):
        a, b = p['positions'][start], p['positions'][end]
        geometry = [self.interpolate(p['shape'], a)]
        geometry += p['shape'][int(a) + 1:math.ceil(b)]
        geometry.append(self.interpolate(p['shape'], b))
        return geometry

    def typical_seconds(self, pid, start, end):
        """Median scheduled travel time over every trip of a pattern; an estimate, never a timetable."""
        key = (pid, start, end)
        if key not in self._ride_cache:
            spans = sorted(t['calls'][end]['arrival'] - t['calls'][start]['departure']
                           for (_, pattern), trips in self.scheduled.items() if pattern == pid for t in trips)
            self._ride_cache[key] = max(60, spans[len(spans) // 2]) if spans else None
        return self._ride_cache[key]

    def last_departure(self, profile, pid, index):
        key = (profile, pid, index)
        if key not in self._last_cache:
            trips = self.scheduled.get((profile, pid), [])
            self._last_cache[key] = max((t['calls'][index]['departure'] for t in trips), default=None)
        return self._last_cache[key]

    def equivalents(self, pid, start, end):
        """Other patterns of the same route/direction serving exactly this platform sequence (e.g. short turns)."""
        key = (pid, start, end)
        if key not in self._twin_cache:
            p = self.patterns[pid]
            stops = [c['stop'] for c in p['calls'][start:end + 1]]
            twins = []
            for other in self.patterns.values():
                if other['id'] == pid or other['route'] != p['route'] or other['direction'] != p['direction']:
                    continue
                sequence = [c['stop'] for c in other['calls']]
                for i in range(len(sequence) - len(stops) + 1):
                    if sequence[i:i + len(stops)] == stops:
                        twins.append((other['id'], i, i + len(stops) - 1))
                        break
            self._twin_cache[key] = twins
        return self._twin_cache[key]

    def segments(self, pid, start, end, calls=None):
        """Station-to-station pieces of a ride; scheduled when trip calls are supplied, otherwise typical estimates."""
        p = self.patterns[pid]
        pieces = []
        for i in range(start, end):
            a, b = p['calls'][i], p['calls'][i + 1]
            piece = {'from': a['station'], 'to': b['station'], 'from_stop': a['stop'], 'to_stop': b['stop'],
                     'geometry': self.geometry(p, i, i + 1)}
            if calls:
                x, y = calls[i - start], calls[i - start + 1]
                piece.update({'departure': x['departure'], 'arrival': y['arrival'], 'seconds': y['arrival'] - x['departure'],
                              'dwell_seconds': y['departure'] - y['arrival'], 'time_kind': 'scheduled_estimate'})
            else:
                piece.update({'seconds': self.typical_seconds(pid, i, i + 1), 'time_kind': 'estimated'})
            pieces.append(piece)
        return pieces

    def ride(self, pid, start, end):
        p = self.patterns[pid]
        if not (0 <= start < end < len(p['calls'])):
            raise ValueError('Invalid ride stop sequence.')
        calls = p['calls'][start:end + 1]
        if not calls[0]['board'] or not calls[-1]['alight']:
            raise ValueError('Boarding or alighting is not allowed at this endpoint.')
        geometry = self.geometry(p, start, end)
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

    def entrance_costs(self, stop, graph):
        """Pathway seconds from a platform to each street entrance of its station (or to it, on the reverse graph)."""
        doors, costs, q, visited = set(self.entrances.get(self.parent(stop), [])), {}, [(0, stop)], set()
        while q and len(costs) < len(doors):
            t, node = heapq.heappop(q)
            if node in visited:
                continue
            visited.add(node)
            if node in doors:
                costs[node] = t
            for target, cost, _ in graph[node]:
                heapq.heappush(q, (t + cost, target))
        return costs

    def street_transfer(self, origin, destination, buffer, why):
        """Explicitly estimated exit → outdoor walk → re-entry when GTFS forbids or lacks an in-station platform change.

        Built only from the station's own GTFS entrances and pathways plus a straight-line outdoor walk; it never
        invents a directed in-station transfer, and it is labelled street-level so the plan shows the re-entry.
        """
        if self.parent(origin) != self.parent(destination):
            return None
        exits, entries = self.entrance_costs(origin, self.pathways), self.entrance_costs(destination, self.reverse_pathways)
        if not exits or not entries:
            return None
        plans = [(out + distance(self.stop_point(a), self.stop_point(b)) / 1.2 + back, a, b, distance(self.stop_point(a), self.stop_point(b)))
                 for a, out in exits.items() for b, back in entries.items()]
        seconds, door_out, door_in, meters = min(plans)
        names = self.stops[door_out].get('stop_name', door_out), self.stops[door_in].get('stop_name', door_in)
        return {'seconds': math.ceil(seconds + buffer), 'walk_seconds': math.ceil(seconds), 'minimum_seconds': 0,
                'buffer_seconds': buffer, 'estimated': True, 'fallback': True, 'street_level': True,
                'via': [door_out, door_in], 'via_names': list(names), 'outdoor_meters': round(meters),
                'source': f'estimated street-level transfer: exit via {names[0]}, walk about {round(meters)} m outdoors, '
                          f're-enter via {names[1]}; {why}'}

    def transfer(self, origin, destination, buffer=0, from_trip=None, to_trip=None, station_change=120):
        """Directed platform constraints; trip-specific GTFS rules remain trip-specific.

        A station with no GTFS pathway data at all gets an explicitly estimated same-station platform change.
        Where GTFS forbids the in-station transfer or its pathways do not connect two platforms, the only option is
        an explicitly estimated street-level exit and re-entry; without reachable entrances there is no transfer.
        """
        rules = self.transfer_rules.get((origin, destination), [])
        applicable = [r for r in rules if (not r['from_trip_id'] or r['from_trip_id'] == from_trip)
                      and (not r['to_trip_id'] or r['to_trip_id'] == to_trip)]
        # Prefer the most specific matching rule, as required by GTFS.
        if applicable:
            specificity = max(bool(r['from_trip_id']) + bool(r['to_trip_id']) for r in applicable)
            applicable = [r for r in applicable if bool(r['from_trip_id']) + bool(r['to_trip_id']) == specificity]
        if any(r['transfer_type'] == '3' for r in applicable):
            return self.street_transfer(origin, destination, buffer, 'GTFS marks the in-station transfer as not possible')
        path = self.pathway_time(origin, destination)
        if path is None and not applicable:
            station = self.parent(origin)
            if station == self.parent(destination) and station in self.stations and station not in self.pathway_stations:
                return {'seconds': math.ceil(station_change + buffer), 'walk_seconds': math.ceil(station_change),
                        'minimum_seconds': 0, 'buffer_seconds': buffer, 'estimated': True, 'fallback': True,
                        'source': 'estimated platform change; this station has no GTFS pathways'}
            return self.street_transfer(origin, destination, buffer, 'GTFS pathways do not connect these platforms inside the station')
        minimum = max([float(r['min_transfer_time'] or 0) for r in applicable] + [0])
        walk = max([float(r['min_walk_time'] or 0) for r in applicable] + [path[0] if path else 0])
        suggested = max([float(r['suggested_buffer_time'] or 0) for r in applicable] + [0])
        return {'seconds': math.ceil(max(minimum, walk + suggested) + buffer),
                'walk_seconds': math.ceil(walk), 'minimum_seconds': minimum, 'buffer_seconds': buffer,
                'source': 'GTFS directed transfers/pathways', 'estimated': path[1] if path else not bool(walk)}

    def options(self, origin, destination, day, route='', time=''):
        """Bounded best-first search for plausible rail paths.

        Repeated traversal of trunk stations and same-line branch changes are allowed (and penalised in ranking)
        because an all-stations journey needs them; the exact feasible trips are evaluated after selection.
        """
        date.fromisoformat(day)
        if origin not in self.stations or destination not in self.stations or origin == destination:
            raise ValueError('Choose two different MBTA stations.')
        if route and route not in COLORS:
            raise ValueError('Unknown line filter.')
        if not any(d == day for d, _ in self.calendar):
            return {'options': [], 'message': 'This date is outside the imported timetable. Choose a published service date.'}
        ready = service_seconds(time) if time else None
        target = self.stations[destination]['point']
        # Admissible-enough lower bound for ranking: straight-line distance at 25 m/s.
        remaining = lambda station: distance(self.stations[station]['point'], target) / 25
        serial = count()
        queue = [(remaining(origin), 0, next(serial), origin, None, [], frozenset([origin]), 0)]
        best, answers, signatures = defaultdict(list), [], set()
        expansions, ended = 0, False
        while queue and len(answers) < 3 and expansions < 20000:
            _, cost, _, station, previous_stop, legs, visited, revisits = heapq.heappop(queue)
            expansions += 1
            if station == destination:
                signature = tuple((x['route'], x['from'], x['to'], tuple(x['stations'])) for x in legs)
                if signature not in signatures:
                    answers.append({'legs': legs, 'transfers': len(legs) - 1, 'approx_minutes': round(cost / 60),
                                    'revisited_stations': revisits,
                                    'estimated_transfers': any(l.get('transfer_estimated') for l in legs),
                                    'street_transfers': any(l.get('transfer_street_level') for l in legs),
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
            origins = {x['from'] for x in legs}
            boarding_stations = [station] + (sorted(self.interchanges[station]) if previous_stop else [])
            entries = []
            for pid, i in (entry for s in boarding_stations for entry in self.starts[s]):
                p = self.patterns[pid]
                if route and p['route'] != route:
                    continue
                cal = self.calendar.get((day, p['route']))
                if not cal or cal['Profile ID'] not in p['profiles']:
                    continue
                entries.append((-len(self.scheduled.get((cal['Profile ID'], pid), [])), pid, i, cal))
            # Busiest pattern first, so a stop sequence is represented by its regular service, not a rare early trip.
            for _, pid, i, cal in sorted(entries):
                p = self.patterns[pid]
                if legs and legs[-1]['pattern'] == pid:
                    continue  # Continuing on the same pattern is already represented by a longer single ride.
                if legs and any(c['station'] == legs[-1]['from'] for c in p['calls'][:i]):
                    continue  # This train already served the previous origin: the longer single ride covers it.
                # Stations the previous train would still reach: changing trains to get there is pointless.
                onward = {c['station'] for c in self.patterns[legs[-1]['pattern']]['calls'][legs[-1]['end'] + 1:]} if legs else set()
                transfer = self.transfer(previous_stop, p['calls'][i]['stop']) if previous_stop else {'seconds': 0}
                if transfer is None:
                    continue
                if ready is not None:
                    last = self.last_departure(cal['Profile ID'], pid, i)
                    if last is None or last < ready + transfer['seconds']:
                        ended = ended or not legs
                        continue
                boarding_revisit = p['calls'][i]['station'] != station and p['calls'][i]['station'] in visited
                for j in range(i + 1, len(p['calls'])):
                    c = p['calls'][j]
                    if not c['alight'] or c['station'] == station or c['station'] in origins or c['station'] in onward:
                        continue
                    signature = (p['route'], tuple(x['stop'] for x in p['calls'][i:j + 1]))
                    if signature in candidate_keys:
                        continue
                    candidate_keys.add(signature)
                    intermediate = {x['station'] for x in p['calls'][i + 1:j + 1]}
                    repeated = len(intermediate & visited) + boarding_revisit
                    leg = self.ride(pid, i, j)
                    if transfer.get('fallback'):
                        leg['transfer_estimated'] = True
                    if transfer.get('street_level'):
                        leg['transfer_street_level'] = True
                    travel = max(1, c['arrival'] - p['calls'][i]['departure'])
                    # Ranking only: exact feasible trips are evaluated after the user selects a path.
                    penalty = (300 if legs else 0) + 300 * repeated + (300 if transfer.get('street_level') else 0)
                    total = cost + travel + transfer['seconds'] + penalty
                    heapq.heappush(queue, (total + remaining(c['station']), total, next(serial), c['station'],
                                           c['stop'], legs + [leg], visited | intermediate | {leg['from']}, revisits + repeated))
        if answers:
            # Drop far slower alternatives (typically loops that re-board the same line) once a sensible path exists.
            limit = min(a['approx_minutes'] for a in answers) * 1.4 + 3
            answers = [a for a in answers if a['approx_minutes'] <= limit]
            message = ''
        elif ended:
            message = (f"Scheduled rail service from {self.stations[origin]['name']} has ended for {day} by service time {clock(ready)}. "
                       'Choose an earlier platform-ready time or the next service date.')
        elif route:
            message = f'No {route} path connects these stations within four rides. Try All lines or add an explicit foot link.'
        else:
            message = 'No directed rail path found within four rides for these stations/date. Add an explicit foot link.'
        return {'options': answers, 'message': message}

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
        result = {'id': str(leg.get('id', ''))[:100], 'mode': leg['mode'], 'from': leg['from'], 'to': leg['to'],
                  'geometry': points, 'geometry_source': source,
                  'distance': round(sum(distance(a, b) for a, b in zip(points, points[1:]))), 'stations': []}
        provider = leg.get('provider_seconds')
        if source == 'google_routes' and isinstance(provider, (int, float)) and 0 < provider < 86400:
            result['provider_seconds'] = int(provider)  # Google's own walking estimate, kept separate from our pace model.
        return result

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
        station_change = number('station_change', 120, 0, 1800)
        result, covered, events, previous, previous_ride = [], set(), [], None, None
        first_board, last_arrival, reason, problems = None, None, '', []
        for index, raw in enumerate(legs):
            leg = self.canonical_leg(raw)
            passage = previous_ride and leg['mode'] == 'ride' and self.transfer(previous_ride['to_stop'], leg['from_stop'], station_change=station_change)
            if previous and previous['to'] != leg['from'] and not passage:
                reason = f"Segment {index + 1} is disconnected from the preceding endpoint. Reorder or replace it."
            item = {**leg, 'status': 'blocked' if reason else 'ok', 'time_kind': 'estimated' if leg['mode'] != 'ride' else 'scheduled_estimate'}
            if reason:
                item.update({'message': reason, 'reason_code': 'disconnected'})
                problems.append(reason)
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
                variants = [(leg['pattern'], leg['start'], leg['end'])] + self.equivalents(leg['pattern'], leg['start'], leg['end'])
                trips = [(trip, pid, s, e) for pid, s, e in variants for trip in (self.scheduled.get((cal['Profile ID'], pid), []) if cal else [])]
                candidates, blocked_transfers, too_late, last_departure = [], 0, 0, None
                for trip, pid, s, e in trips:
                    a, b = trip['calls'][s], trip['calls'][e]
                    if not a['board'] or not b['alight']:
                        continue
                    continuous = bool(previous_ride and previous_ride['trip_id'] == trip['id'] and previous_ride['to_stop'] == a['stop'])
                    transfer = {'seconds': 0, 'source': 'same train' if continuous else 'platform ready'}
                    if previous_ride and not continuous:
                        transfer = self.transfer(previous_ride['to_stop'], a['stop'], buffer, previous_ride['trip_id'], trip['id'], station_change)
                    if transfer is None:
                        blocked_transfers += 1
                        continue
                    if a['departure'] < ready + transfer['seconds']:
                        too_late += 1
                        last_departure = a['departure'] if last_departure is None else max(last_departure, a['departure'])
                        continue
                    candidates.append((b['arrival'], a['departure'], trip['id'], trip, transfer, continuous, (pid, s, e)))
                if not candidates:
                    origin, headsign = self.stations[leg['from']]['name'], p['headsign']
                    if not cal:
                        code, why = 'outside_feed', f'{day} is outside the published schedule coverage; no timetable exists for it in this snapshot.'
                    elif not trips:
                        code, why = 'no_trips_for_profile', f"{p['route']} toward {headsign} has no trips on the {day} timetable along this exact stop pattern. Preview the path again for this date."
                    elif too_late and not blocked_transfers:
                        code, why = 'no_service_remaining', (f"The last scheduled {p['route']} departure from {origin} toward {headsign} on {day} is "
                                                             f"{clock(last_departure)}; you would be ready at {clock(ready)}. Start earlier or use the next service date.")
                    elif blocked_transfers and not too_late:
                        code, why = 'transfer_not_permitted', (f"GTFS does not permit a directed platform transfer from {previous_ride['to_stop']} to {leg['from_stop']} "
                                                               f"at {origin}. Choose a path via another platform or add an explicit foot link.")
                    else:
                        code, why = 'no_service_remaining', (f"No permitted {p['route']} departure from {origin} toward {headsign} remains on {day} after {clock(ready)} "
                                                             f"(last scheduled {clock(last_departure)}; {blocked_transfers} earlier trips also blocked by transfer rules).")
                    # Keep the plan timed: continue downstream with explicitly estimated durations, never invented trips.
                    estimate = self.typical_seconds(p['id'], leg['start'], leg['end']) or 0
                    change = {'seconds': 0, 'source': 'platform ready'}
                    if previous_ride:
                        change = self.transfer(previous_ride['to_stop'], leg['from_stop'], buffer, station_change=station_change) or {
                            'seconds': math.ceil(station_change + buffer), 'estimated': True, 'source': 'estimated platform change'}
                    item.update({'status': 'unavailable', 'reason_code': code, 'message': why, 'time_kind': 'estimated',
                                 'last_departure': last_departure, 'start_time': ready, 'trip_id': None,
                                 'wait_seconds': 0, 'transfer_seconds': change['seconds'], 'transfer': change, 'travel_seconds': estimate,
                                 'estimated_arrival': ready + change['seconds'] + estimate, 'continuous': False,
                                 'segments': self.segments(p['id'], leg['start'], leg['end'])})
                    problems.append(why)
                    if change['seconds']:
                        events.append({'mode': 'transfer', 'from_stop': previous_ride['to_stop'], 'to_stop': leg['from_stop'],
                                       'from': previous_ride['to'], 'to': leg['from'], 'seconds': change['seconds'],
                                       'time_kind': 'estimated', 'source': change['source']})
                    events.append({'mode': 'estimated_ride', 'seconds': estimate, 'time_kind': 'estimated', 'reason_code': code})
                    ready = item['estimated_arrival']
                    previous_ride = item
                else:
                    _, dep, _, trip, transfer, continuous, (pid, s, e) = min(candidates, key=lambda c: (c[0], c[1], c[2]))
                    if pid != leg['pattern']:
                        # The feasible train runs an equivalent pattern (same platforms, e.g. a short turn): adopt its identity.
                        leg = {**self.ride(pid, s, e), 'id': leg['id']}
                        item.update(leg)
                        p = self.patterns[pid]
                    arrival = trip['calls'][e]['arrival']
                    wait = 0 if continuous else dep - ready - transfer['seconds']
                    travel = arrival - (ready if continuous else dep)
                    calls = trip['calls'][s:e + 1]
                    item.update({'start_time': ready, 'departure': dep, 'arrival': arrival, 'wait_seconds': wait,
                        'travel_seconds': travel, 'transfer_seconds': transfer['seconds'], 'transfer': transfer,
                        'trip_id': trip['id'], 'service_id': trip['service'], 'profile_id': cal['Profile ID'],
                        'continuous': continuous, 'headsign': calls[0]['headsign'],
                        'stop_calls': [{**c} for c in calls], 'segments': self.segments(pid, s, e, calls)})
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
        totals = {mode: sum(e['seconds'] for e in events if e['mode'] == mode)
                  for mode in ('ride', 'wait', 'transfer', 'access', 'run', 'walk', 'estimated_ride')}
        unavailable = [i + 1 for i, l in enumerate(result) if l['status'] == 'unavailable']
        return {'legs': result, 'events': events, 'covered': sorted(covered),
                'missing': sorted(set(self.stations) - covered), 'status': 'partial' if problems else 'ok',
                'message': problems[0] if problems else '', 'problems': problems,
                'summary': {'elapsed': ready - start_time, 'first_board': first_board, 'finish': ready,
                            'unavailable_legs': unavailable, 'estimated': bool(unavailable),
                            'record_proxy_seconds': last_arrival - first_board if first_board is not None else None,
                            'foot_meters': sum(l.get('distance', 0) for l in result if l['mode'] != 'ride' and l['status'] == 'ok'), **totals},
                'dataset': self.manifest['sha256'], 'ruleset': 'rail-rehearsal-v1', 'coverage_label': 'Rail rehearsal; Silver Line and approved inventory still required'}
