#!/usr/bin/env python3
"""Local Google Maps / MBTA track-following itinerary editor."""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.rail_schedule.itinerary import RailNetwork, COLORS

STATIC = Path(__file__).resolve().parent / 'static'
MY_MAP = 'https://www.google.com/maps/d/u/0/edit?mid=1uOrMD32-8alM_w2tyQ-Xio6b6jcxRyk'


def network_kml(network):
    root = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
    doc = ET.SubElement(root, 'Document')
    ET.SubElement(doc, 'name').text = 'MBTA rail tracks and stations · pinned GTFS'
    ET.SubElement(doc, 'description').text = 'Rail-only geographic reference, not a timetable or approved record inventory. Source SHA-256: ' + network.manifest['sha256']
    for line in network.metadata()['lines']:
        p = ET.SubElement(doc, 'Placemark')
        ET.SubElement(p, 'name').text = line['route'] + ' · ' + line['shape_id']
        color = COLORS[line['route']].lstrip('#')
        style = ET.SubElement(ET.SubElement(p, 'Style'), 'LineStyle')
        ET.SubElement(style, 'color').text = 'bb' + color[4:6] + color[2:4] + color[:2]
        ET.SubElement(style, 'width').text = '3'
        ET.SubElement(ET.SubElement(p, 'LineString'), 'coordinates').text = ' '.join(f'{lng},{lat},0' for lat, lng in line['geometry'])
    for s in network.stations.values():
        p = ET.SubElement(doc, 'Placemark')
        ET.SubElement(p, 'name').text = s['name']
        ET.SubElement(p, 'description').text = s['id'] + ' · ' + ', '.join(s['routes'])
        lat, lng = s['point']
        ET.SubElement(ET.SubElement(p, 'Point'), 'coordinates').text = f'{lng},{lat},0'
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def kml_document(network, scenario):
    """Own MBTA/user-authored geometry only; never persist Google-provided routes."""
    root = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
    doc = ET.SubElement(root, 'Document')
    ET.SubElement(doc, 'name').text = str(scenario.get('name', 'T Run itinerary'))[:150]
    ET.SubElement(doc, 'description').text = ('Rail rehearsal, not full-record completion. MBTA GTFS ' + network.manifest['sha256'] +
        '. Track paths are source geometry, not evidence of operation. Google-derived foot geometry is omitted.')
    for i, raw in enumerate(scenario.get('legs', [])):
        leg = network.canonical_leg(raw)
        if leg['geometry_source'] == 'google_routes':
            continue
        mark = ET.SubElement(doc, 'Placemark')
        a, b = network.stations[leg['from']]['name'], network.stations[leg['to']]['name']
        ET.SubElement(mark, 'name').text = f"{i + 1}. {leg.get('route', leg['mode'].title())}: {a} → {b}"
        ET.SubElement(mark, 'description').text = f"{leg['geometry_source']}; {leg['from']} → {leg['to']}. " + ('Stops: ' + ', '.join(network.stations[s]['name'] for s in leg['stations']) if leg['mode'] == 'ride' else 'Estimated foot link; inspect street access.')
        line_style = ET.SubElement(ET.SubElement(mark, 'Style'), 'LineStyle')
        color = COLORS.get(leg.get('route'), '#8056d9').lstrip('#')
        ET.SubElement(line_style, 'color').text = 'ff' + color[4:6] + color[2:4] + color[:2]
        ET.SubElement(line_style, 'width').text = '6'
        line = ET.SubElement(mark, 'LineString')
        ET.SubElement(line, 'tessellate').text = '1'
        ET.SubElement(line, 'coordinates').text = ' '.join(f'{lng},{lat},0' for lat, lng in leg['geometry'])
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def handler(network):
    class Handler(BaseHTTPRequestHandler):
        def send(self, body, mime='application/json; charset=utf-8', status=200, filename=None):
            if not isinstance(body, bytes):
                body = json.dumps(body, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            parsed = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                if parsed.path == '/api/network':
                    return self.send(network.metadata())
                if parsed.path == '/api/config':
                    return self.send({'google_maps_key': os.environ.get('GOOGLE_MAPS_API_KEY', ''), 'my_maps_url': MY_MAP})
                if parsed.path == '/api/options':
                    return self.send(network.options(query.get('from'), query.get('to'), query.get('date', ''), query.get('route', '')))
                if parsed.path == '/api/export/network.kml':
                    return self.send(network_kml(network), 'application/vnd.google-earth.kml+xml', filename='MBTA-rail-tracks.kml')
                files = {'/': ('index.html', 'text/html; charset=utf-8'),
                         '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                         '/map.js': ('map.js', 'text/javascript; charset=utf-8'),
                         '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if parsed.path in files:
                    f, mime = files[parsed.path]
                    return self.send((STATIC / f).read_bytes(), mime)
                return self.send({'error': 'Not found'}, status=404)
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                return self.send({'error': str(exc)}, status=400)

        def do_POST(self):
            # This local tool accepts JSON from its own origin only.
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.send({'error': 'Use the local editor origin.'}, status=403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4_000_000:
                    return self.send({'error': 'Scenario payload must be under 4 MB.'}, status=413)
                scenario = json.loads(self.rfile.read(length))
                if not isinstance(scenario, dict):
                    raise ValueError('Expected a scenario object.')
                if urlparse(self.path).path == '/api/evaluate':
                    return self.send(network.evaluate(scenario))
                if urlparse(self.path).path == '/api/export/kml':
                    network.evaluate(scenario)  # Validate modes, sequence, assumptions and payload limits.
                    return self.send(kml_document(network, scenario), 'application/vnd.google-earth.kml+xml', filename='t-run-itinerary.kml')
                return self.send({'error': 'Not found'}, status=404)
            except (ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
                return self.send({'error': str(exc)}, status=400)
    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, default=ROOT / 'output')
    p.add_argument('--gtfs', type=Path, help='Matching archived GTFS ZIP; defaults to manifest archive.')
    p.add_argument('--port', type=int, default=8001)
    p.add_argument('--host', default='127.0.0.1')
    args = p.parse_args()
    print('Loading pinned rail schedules, directed pathways, and track geometry…', flush=True)
    network = RailNetwork(args.data, args.gtfs)
    server = ThreadingHTTPServer((args.host, args.port), handler(network))
    print(f'Map editor ready: http://{args.host}:{args.port} ({len(network.patterns)} rail patterns)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
