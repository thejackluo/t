"""Editor HTTP and Google My Maps KML integration checks; no Google requests."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from backend.rail_schedule.itinerary import RailNetwork, ROOT
from frontend.map_editor.server import handler, kml_document, network_kml


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

    def test_kml_contains_actual_track_coordinates_and_omits_google_geometry(self):
        rail = self.direct()
        foot = {'mode': 'run', 'from': 'place-pktrm', 'to': 'place-dwnxg',
                'geometry': [self.n.stations[s]['point'] for s in ('place-pktrm', 'place-dwnxg')],
                'geometry_source': 'google_routes'}
        parsed = ET.fromstring(kml_document(self.n, self.scenario([rail, foot])))
        ns = {'k': 'http://www.opengis.net/kml/2.2'}
        self.assertEqual(len(parsed.findall('.//k:Placemark', ns)), 1)
        coords = parsed.find('.//k:coordinates', ns).text.split()
        self.assertEqual(len(coords), len(rail['geometry']))
        self.assertTrue(coords[0].startswith(str(rail['geometry'][0][1])))
        reference = ET.fromstring(network_kml(self.n))
        self.assertEqual(len(reference.findall('.//k:Point', ns)), 125)

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
