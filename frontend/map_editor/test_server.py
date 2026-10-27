"""Editor HTTP and Google My Maps KML integration checks; no Google requests."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from backend.rail_schedule.itinerary import RailNetwork, ROOT
from unittest.mock import patch

from frontend.map_editor.server import ApiError, decode_polyline, foot_route, handler, kml_document, network_kml


class EditorServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = ROOT / 'output/manifest.json'
        if not manifest.exists():
            raise unittest.SkipTest('Generate schedule exports and retain their GTFS archive first.')
        source = json.loads(manifest.read_text())
        if not (ROOT / source['local_archive']).exists():
            raise unittest.SkipTest('Matching pinned GTFS archive is required for geometry tests.')
        cls.n = RailNetwork()

    def scenario(self, legs):
        return {'name': 'Test route', 'date': '2026-10-22', 'time': '08:00', 'legs': legs}

    def direct(self):
        return self.n.options('place-alfcl', 'place-pktrm', '2026-10-22', 'Red')['options'][0]['legs'][0]

    def test_kml_contains_actual_track_coordinates_and_keeps_run_legs_without_google_geometry(self):
        rail = self.direct()
        a, b = (self.n.stations[s]['point'] for s in ('place-pktrm', 'place-dwnxg'))
        foot = {'mode': 'run', 'from': 'place-pktrm', 'to': 'place-dwnxg',
                'geometry': [a, [(a[0] + b[0]) / 2 + 0.001, (a[1] + b[1]) / 2], b], 'geometry_source': 'google_routes'}
        parsed = ET.fromstring(kml_document(self.n, self.scenario([rail, foot])))
        ns = {'k': 'http://www.opengis.net/kml/2.2'}
        marks = parsed.findall('.//k:Placemark', ns)
        self.assertEqual(len(marks), 2)
        coords = marks[0].find('.//k:coordinates', ns).text.split()
        self.assertEqual(len(coords), len(rail['geometry']))
        self.assertTrue(coords[0].startswith(str(rail['geometry'][0][1])))
        run = marks[1]
        self.assertTrue(run.find('k:name', ns).text.startswith('2. Run:'))
        self.assertEqual(run.find('.//k:coordinates', ns).text.split(), [f'{a[1]},{a[0]},0', f'{b[1]},{b[0]},0'])
        self.assertIn('Google street route omitted', run.find('k:description', ns).text)
        self.assertNotIn(str(foot['geometry'][1][0]), ET.tostring(parsed, encoding='unicode'))
        reference = ET.fromstring(network_kml(self.n))
        self.assertEqual(len(reference.findall('.//k:Point', ns)), 125)

    def test_server_side_street_routes_need_a_key_and_keep_station_anchors(self):
        self.assertEqual(decode_polyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@'), [[38.5, -120.2], [40.7, -120.95], [43.252, -126.453]])
        with patch.dict('os.environ', {'GOOGLE_ROUTES_API_KEY': ''}):
            with self.assertRaises(ApiError) as exc:
                foot_route(self.n, 'place-kencl', 'place-fenwy')
            self.assertEqual(exc.exception.status, 404)
        a, b = self.n.stations['place-kencl']['point'], self.n.stations['place-fenwy']['point']
        payload = json.dumps({'routes': [{'distanceMeters': 1234, 'duration': '900s', 'polyline': {'encodedPolyline': '_p~iF~ps|U_ulLnnqC'}}]}).encode()
        seen = {}
        def fetch(request):
            seen['body'] = json.loads(request.data)
            seen['mask'] = request.get_header('X-goog-fieldmask')
            return payload
        with patch.dict('os.environ', {'GOOGLE_ROUTES_API_KEY': 'server-key'}):
            route = foot_route(self.n, 'place-kencl', 'place-fenwy', fetch)
        self.assertEqual(seen['body']['travelMode'], 'WALK')
        self.assertIn('routes.polyline.encodedPolyline', seen['mask'])
        self.assertEqual((route['geometry'][0], route['geometry'][-1]), (a, b))
        self.assertEqual((route['provider_distance'], route['provider_seconds'], route['geometry_source']), (1234, 900, 'google_routes'))
        leg = self.n.canonical_leg({'mode': 'run', **route})
        self.assertEqual(leg['provider_seconds'], 900)
        self.assertNotIn('provider_seconds', self.n.canonical_leg({'mode': 'run', **route, 'geometry_source': 'user_drawn'}))

    def test_http_editor_delivers_assets_and_track_export(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.n))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        try:
            for path in ('/', '/app.js', '/map.js', '/style.css', '/api/network'):
                with urlopen(base + path) as r:
                    self.assertEqual(r.status, 200)
            with urlopen(base + '/api/export/network.kml') as r:
                self.assertIn('attachment', r.headers['Content-Disposition'])
                ET.fromstring(r.read())
            body = json.dumps(self.scenario([self.direct()])).encode()
            req = Request(base + '/api/evaluate', data=body, headers={'Content-Type': 'application/json', 'Origin': base})
            with urlopen(req) as r:
                self.assertEqual(json.load(r)['status'], 'ok')
            req.add_header('Origin', 'https://unrelated.example')
            with self.assertRaises(HTTPError) as exc:
                urlopen(req)
            self.assertEqual(exc.exception.code, 403)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
