#!/usr/bin/env python3
"""Local Google Maps / MBTA track-following itinerary editor."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.rail_schedule.itinerary import RailNetwork, COLORS
from backend.rail_schedule.backtracking import analyze

STATIC = Path(__file__).resolve().parent / 'static'
MY_MAP = 'https://www.google.com/maps/d/u/0/edit?mid=1uOrMD32-8alM_w2tyQ-Xio6b6jcxRyk'
JSON_MIME = 'application/json; charset=utf-8'
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/index.html': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/map.js': ('map.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8'),
          '/demo': ('demo.html', 'text/html; charset=utf-8'),
          '/demo.html': ('demo.html', 'text/html; charset=utf-8'),
          '/demo.js': ('demo.js', 'text/javascript; charset=utf-8'),
          '/launch': ('launch.html', 'text/html; charset=utf-8'),
          '/launch.js': ('launch.js', 'text/javascript; charset=utf-8')}
REASONS = {200: 'OK', 400: 'Bad Request', 403: 'Forbidden', 404: 'Not Found',
           405: 'Method Not Allowed', 413: 'Payload Too Large', 500: 'Internal Server Error'}


ROUTES_URL = 'https://routes.googleapis.com/directions/v2:computeRoutes'


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def decode_polyline(encoded):
    """Google encoded polyline → [[lat, lng], ...]."""
    points, index, lat, lng = [], 0, 0, 0
    while index < len(encoded):
        for which in (0, 1):
            result, shift = 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += delta
            else:
                lng += delta
        points.append([round(lat / 1e5, 6), round(lng / 1e5, 6)])
    return points


def foot_route(network, origin, destination, fetch=None):
    """Server-side pedestrian route from the Routes API; needs a server key, never the browser key."""
    key = os.environ.get('GOOGLE_ROUTES_API_KEY', '')
    if not key:
        raise ApiError(404, 'Street routing is not configured on this server. Connect Google Maps in the browser or draw the path.')
    if origin not in network.stations or destination not in network.stations or origin == destination:
        raise ApiError(400, 'Choose two different MBTA stations.')
    a, b = network.stations[origin]['point'], network.stations[destination]['point']
    body = json.dumps({'origin': {'location': {'latLng': {'latitude': a[0], 'longitude': a[1]}}},
                       'destination': {'location': {'latLng': {'latitude': b[0], 'longitude': b[1]}}},
                       'travelMode': 'WALK', 'polylineQuality': 'HIGH_QUALITY'}).encode()
    request = urllib.request.Request(ROUTES_URL, data=body, headers={
        'Content-Type': 'application/json', 'X-Goog-Api-Key': key,
        'X-Goog-FieldMask': 'routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline'})
    try:
        if fetch:
            payload = fetch(request)
        else:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = response.read()
    except urllib.error.HTTPError as exc:
        raise ApiError(502, f'Google Routes API rejected the request ({exc.code}). Check the server key, Routes API enablement, and billing.') from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ApiError(502, 'Could not reach the Google Routes API.') from exc
    routes = json.loads(payload).get('routes') or []
    if not routes:
        raise ApiError(404, 'No pedestrian route returned. Check entrances or draw a path manually.')
    route = routes[0]
    points = decode_polyline(route['polyline']['encodedPolyline'])
    points[0], points[-1] = a, b  # Station anchors stay fixed.
    return {'from': origin, 'to': destination, 'geometry': points, 'geometry_source': 'google_routes',
            'provider_distance': int(route.get('distanceMeters', 0)), 'provider_seconds': int(str(route.get('duration', '0s')).rstrip('s') or 0),
            'note': 'Google pedestrian route; session-only, inspect entrances and crossings.'}


def same_origin(origin, host):
    """Accept the browser's own origin over local HTTP or a deployed HTTPS proxy."""
    if not origin:
        return True
    return urlparse(origin).netloc == (host or '').split(',')[0].strip()


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
        google = leg['geometry_source'] == 'google_routes'
        if google:  # Keep the leg and its numbering; replace only the session-only Google geometry with a station-to-station line.
            leg = {**leg, 'geometry': [network.stations[leg['from']]['point'], network.stations[leg['to']]['point']],
                   'geometry_source': 'straight_line_sketch'}
        mark = ET.SubElement(doc, 'Placemark')
        a, b = network.stations[leg['from']]['name'], network.stations[leg['to']]['name']
        ET.SubElement(mark, 'name').text = f"{i + 1}. {leg.get('route', leg['mode'].title())}: {a} → {b}"
        ET.SubElement(mark, 'description').text = f"{leg['geometry_source']}; {leg['from']} → {leg['to']}. " + ('Stops: ' + ', '.join(network.stations[s]['name'] for s in leg['stations']) if leg['mode'] == 'ride' else ('Google street route omitted (session-only); straight line between stations, draw the street path in My Maps. ' if google else '') + 'Estimated foot link; inspect street access.')
        line_style = ET.SubElement(ET.SubElement(mark, 'Style'), 'LineStyle')
        color = COLORS.get(leg.get('route'), '#8056d9').lstrip('#')
        ET.SubElement(line_style, 'color').text = 'ff' + color[4:6] + color[2:4] + color[:2]
        ET.SubElement(line_style, 'width').text = '6'
        line = ET.SubElement(mark, 'LineString')
        ET.SubElement(line, 'tessellate').text = '1'
        ET.SubElement(line, 'coordinates').text = ' '.join(f'{lng},{lat},0' for lat, lng in leg['geometry'])
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def get_response(network, path, query):
    if path == '/api/network':
        return 200, JSON_MIME, network.metadata(), None
    if path == '/api/config':
        return 200, JSON_MIME, {'google_maps_key': os.environ.get('GOOGLE_MAPS_API_KEY', ''), 'my_maps_url': MY_MAP,
                                'foot_routing': bool(os.environ.get('GOOGLE_ROUTES_API_KEY'))}, None
    if path == '/api/foot-route':
        return 200, JSON_MIME, foot_route(network, query.get('from'), query.get('to')), None
    if path == '/api/options':
        return 200, JSON_MIME, network.options(query.get('from'), query.get('to'), query.get('date', ''), query.get('route', ''), query.get('time', ''), query.get('mode', 'rail')), None
    if path == '/api/export/network.kml':
        return 200, 'application/vnd.google-earth.kml+xml', network_kml(network), 'MBTA-rail-tracks.kml'
    if path in ASSETS:
        name, mime = ASSETS[path]
        asset = STATIC / name
        if asset.is_file():
            return 200, mime, asset.read_bytes(), None
    raise ApiError(404, 'Not found')


def post_response(network, path, raw):
    if not 0 < len(raw) <= 4_000_000:
        raise ApiError(413, 'Scenario payload must be under 4 MB.')
    try:
        scenario = json.loads(raw)
    except ValueError as exc:
        raise ApiError(400, 'Invalid JSON payload.') from exc
    if not isinstance(scenario, dict):
        raise ApiError(400, 'Expected a scenario object.')
    if path == '/api/evaluate':
        return 200, JSON_MIME, network.evaluate(scenario), None
    if path == '/api/analyze':
        return 200, JSON_MIME, analyze(network, scenario), None
    if path == '/api/export/kml':
        network.evaluate(scenario)  # Validate modes, sequence, assumptions and payload limits.
        return 200, 'application/vnd.google-earth.kml+xml', kml_document(network, scenario), 't-run-itinerary.kml'
    raise ApiError(404, 'Not found')


def wsgi_application(network):
    """No-dependency WSGI entrypoint used by Vercel and local smoke checks."""
    def application(environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET').upper()
        path = environ.get('PATH_INFO') or '/'
        query = {k: v[0] for k, v in parse_qs(environ.get('QUERY_STRING', '')).items()}
        host = environ.get('HTTP_X_FORWARDED_HOST') or environ.get('HTTP_HOST', '')
        try:
            if method in ('GET', 'HEAD'):
                status, mime, body, filename = get_response(network, path, query)
            elif method == 'POST':
                if not same_origin(environ.get('HTTP_ORIGIN'), host):
                    raise ApiError(403, 'Use the editor origin.')
                length = int(environ.get('CONTENT_LENGTH') or 0)
                raw = environ['wsgi.input'].read(length) if length else b''
                status, mime, body, filename = post_response(network, path, raw)
            else:
                raise ApiError(405, 'Method not allowed.')
        except ApiError as exc:
            status, mime, body, filename = exc.status, JSON_MIME, {'error': str(exc)}, None
        except (ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
            status, mime, body, filename = 400, JSON_MIME, {'error': str(exc)}, None
        if not isinstance(body, bytes):
            body = json.dumps(body, allow_nan=False).encode()
        headers = [('Content-Type', mime), ('Content-Length', str(len(body))),
                   ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')]
        if filename:
            headers.append(('Content-Disposition', f'attachment; filename="{filename}"'))
        start_response(f'{status} {REASONS.get(status, "Error")}', headers)
        return [b'' if method == 'HEAD' else body]
    return application


def handler(network):
    class Handler(BaseHTTPRequestHandler):
        def send(self, body, mime=JSON_MIME, status=200, filename=None):
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
                status, mime, body, filename = get_response(network, parsed.path, query)
                return self.send(body, mime, status, filename)
            except ApiError as exc:
                return self.send({'error': str(exc)}, status=exc.status)
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                return self.send({'error': str(exc)}, status=400)

        def do_POST(self):
            # Browser posts must come from the page's own origin, including behind an HTTPS proxy.
            host = self.headers.get('x-forwarded-host') or self.headers.get('Host', '')
            if not same_origin(self.headers.get('Origin'), host):
                return self.send({'error': 'Use the editor origin.'}, status=403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4_000_000:
                    raise ApiError(413, 'Scenario payload must be under 4 MB.')
                raw = self.rfile.read(length)
                status, mime, body, filename = post_response(network, urlparse(self.path).path, raw)
                return self.send(body, mime, status, filename)
            except ApiError as exc:
                return self.send({'error': str(exc)}, status=exc.status)
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
