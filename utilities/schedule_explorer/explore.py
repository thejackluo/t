#!/usr/bin/env python3
"""Serve the validated MBTA rail snapshot and its interactive explorer. No dependencies."""
import argparse
import csv
import gzip
import json
import statistics
from collections import defaultdict
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / 'static'
COLORS = {'Red': '#d53535', 'Mattapan': '#ad3d38', 'Orange': '#db770a', 'Blue': '#2867c9',
          'Green-B': '#25815c', 'Green-C': '#25815c', 'Green-D': '#25815c', 'Green-E': '#25815c'}


def seconds(value):
    h, m, s = map(int, value.split(':'))
    return h * 3600 + m * 60 + s


def summary(events):
    board = sorted((e for e in events if e['board']), key=lambda e: e['seconds'])
    gaps = [(b['seconds'] - a['seconds']) / 60 for a, b in zip(board, board[1:])]
    return {'first': board[0]['seconds'] if board else None, 'last': board[-1]['seconds'] if board else None,
            'count': len(board), 'median': statistics.median(gaps) if gaps else None,
            'min': min(gaps) if gaps else None, 'max': max(gaps) if gaps else None,
            'arrival_only': bool(events) and not board}


class Dataset:
    def __init__(self, directory):
        self.directory = directory
        self.manifest = json.loads((directory / 'manifest.json').read_text())
        self.stations = [{
            'id': r['Station ID'], 'name': r['Station name'], 'routes': r['Rail routes'].split(', ')
        } for r in self.rows('stations')]
        self.station_ids = {s['id'] for s in self.stations}
        self.calendar = list(self.rows('service_calendar'))
        self.cal_index = {(r['Service date'], r['Route']): r for r in self.calendar}
        self.directions = defaultdict(dict)
        for r in self.rows('station_hours'):
            self.directions[r['Route']][r['Direction ID']] = r['Direction']
        self.events = defaultdict(list)
        for r in self.rows('departures'):
            e = {'seconds': int(r['Departure service seconds']), 'arrival': r['Arrival service time'],
                 'time': r['Departure service time'], 'destination': r['Destination'],
                 'platform': r['Platform stop ID'], 'trip': r['Trip ID'],
                 'board': r['Can board'] == '1', 'alight': r['Can alight'] == '1',
                 'sequence': int(r['Stop sequence']), 'timepoint': r['Timepoint']}
            self.events[(r['Profile ID'], r['Station ID'], r['Direction ID'])].append(e)
        for es in self.events.values():
            es.sort(key=lambda e: (e['seconds'], e['trip']))
        self.holidays = list(self.rows('holidays'))

    def rows(self, name):
        with gzip.open(self.directory / (name + '.csv.gz'), 'rt', newline='', encoding='utf-8') as f:
            yield from csv.DictReader(f)

    def metadata(self):
        return {'manifest': self.manifest, 'stations': self.stations,
                'routes': [{'id': r, 'color': COLORS.get(r, '#526071'), 'directions': self.directions[r]}
                           for r in self.manifest['routes']],
                'dates': sorted({r['Service date'] for r in self.calendar}),
                'holidays': [r for r in self.holidays if r['Route'] == self.manifest['routes'][0]]}

    def selection(self, query):
        route = query.get('route', ['Red'])[0]
        station = query.get('station', ['place-pktrm'])[0]
        direction = query.get('direction', ['0'])[0]
        day = query.get('date', [self.calendar[0]['Service date']])[0]
        destination = query.get('destination', [''])[0]
        date.fromisoformat(day)
        if route not in self.manifest['routes'] or station not in self.station_ids or direction not in ('0', '1'):
            raise ValueError('Unknown route, station, or direction')
        cal = self.cal_index.get((day, route))
        events = self.events.get((cal['Profile ID'], station, direction), []) if cal else []
        selected = [e for e in events if not destination or e['destination'] == destination]
        comparisons = []
        for c in self.calendar:
            if c['Route'] != route:
                continue
            es = self.events.get((c['Profile ID'], station, direction), [])
            es = [e for e in es if not destination or e['destination'] == destination]
            comparisons.append({'date': c['Service date'], 'day': c['Day'], 'holiday': c['Holiday name'],
                                'pattern': c['Service description'], 'profile': c['Profile ID'], **summary(es)})
        return {'published': cal is not None, 'calendar': cal, 'summary': summary(selected), 'events': selected,
                'destinations': sorted({e['destination'] for e in events}),
                'platforms': sorted({e['platform'] for e in events}), 'comparisons': comparisons}

    def directory_rows(self, query):
        route, day, direction = query['route'][0], query['date'][0], query['direction'][0]
        cal = self.cal_index.get((day, route))
        return [{**s, **summary(self.events.get((cal['Profile ID'], s['id'], direction), []) if cal else [])}
                for s in self.stations if route in s['routes']]


def handler(dataset):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            try:
                if parsed.path == '/api/meta':
                    return self.send_json(dataset.metadata())
                if parsed.path == '/api/station':
                    return self.send_json(dataset.selection(query))
                if parsed.path == '/api/stations':
                    dataset.selection(query)  # Validate route, date and direction consistently.
                    return self.send_json(dataset.directory_rows(query))
                files = {'/': ('index.html', 'text/html; charset=utf-8'),
                         '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                         '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if parsed.path == '/download/workbook':
                    return self.send_file(dataset.directory / 'MBTA_Rail_Scheduling.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', True)
                if parsed.path in files:
                    name, mime = files[parsed.path]
                    return self.send_file(STATIC_DIR / name, mime)
                self.send_error(404)
            except (ValueError, KeyError) as exc:
                self.send_json({'error': str(exc)}, 400)

        def send_json(self, value, status=200):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def send_file(self, path, mime, attachment=False):
            body = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            if attachment:
                self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
            self.end_headers()
            self.wfile.write(body)

    return Handler


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, default=ROOT / 'output')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8000)
    args = p.parse_args()
    if not (args.data / 'manifest.json').exists():
        p.error('Schedule data is missing. From the repository root run python3 -m backend.rail_schedule.build_schedule; see backend/rail_schedule/README.md.')
    print('Loading the validated schedule snapshot…', flush=True)
    dataset = Dataset(args.data)
    server = ThreadingHTTPServer((args.host, args.port), handler(dataset))
    print(f'Rail explorer ready: http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
