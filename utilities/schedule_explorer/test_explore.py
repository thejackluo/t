"""Data-integrity checks for the explorer against the validated schedule exports."""
import unittest
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

from .explore import Dataset, handler, seconds
from backend.rail_schedule.schedule_lookup import lookup


class ExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[2] / 'output'
        if not (cls.path / 'manifest.json').exists():
            raise unittest.SkipTest('Generate the schedule snapshot before running data-integration checks')
        cls.data = Dataset(cls.path)

    def test_moved_static_assets_and_api_are_served(self):
        with ThreadingHTTPServer(('127.0.0.1', 0), handler(self.data)) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                for path, content_type in [('/', 'text/html'), ('/app.js', 'text/javascript'), ('/style.css', 'text/css')]:
                    with self.subTest(path=path), urlopen(base + path, timeout=5) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn(content_type, response.headers['Content-Type'])
                        self.assertTrue(response.read())
                with urlopen(base + '/api/meta', timeout=5) as response:
                    metadata = json.load(response)
                    self.assertEqual(metadata['manifest']['sha256'], self.data.manifest['sha256'])
            finally:
                server.shutdown()
                thread.join(timeout=5)

    def select(self, **kwargs):
        args = {'date': '2026-10-22', 'route': 'Red', 'station': 'place-pktrm', 'direction': '0'}
        args.update(kwargs)
        return self.data.selection({k: [v] for k, v in args.items()})

    def test_destination_wait_matches_validated_lookup(self):
        result = self.select(destination='Ashmont')
        expected = lookup(self.path, '2026-10-22', 'Red', 'place-pktrm', '0', 28800, 'Ashmont')
        next_train = next(e for e in result['events'] if e['board'] and e['seconds'] >= 28800)
        self.assertEqual(next_train['trip'], expected['departures'][0]['Trip ID'])
        self.assertEqual(next_train['seconds'] - 28800, expected['scheduled_wait_seconds'])

    def test_friday_overnight_and_holiday_patterns(self):
        self.assertEqual(self.select(date='2026-10-23')['summary']['last'], seconds('25:45:00'))
        holiday = self.select(date='2026-11-26')
        self.assertEqual(holiday['calendar']['Holiday name'], 'Thanksgiving Day')
        self.assertEqual(holiday['summary']['count'], 181)

    def test_terminal_arrival_is_not_boarding_and_unpublished_is_empty(self):
        terminal = self.select(station='place-brntn')
        self.assertTrue(terminal['summary']['arrival_only'])
        self.assertEqual(terminal['summary']['count'], 0)
        outside = self.select(date='2026-12-25')
        self.assertFalse(outside['published'])
        self.assertEqual(outside['events'], [])

    def test_explorer_hours_match_exported_summaries(self):
        days = {'2026-10-22', '2026-10-23', '2026-10-24', '2026-10-25', '2026-11-26', '2026-11-27'}
        checked = 0
        for r in self.data.rows('station_hours'):
            if r['Service date'] not in days:
                continue
            result = self.select(date=r['Service date'], route=r['Route'], station=r['Station ID'], direction=r['Direction ID'])['summary']
            self.assertEqual(result['count'], int(r['Boardable departures']))
            if result['count']:
                self.assertEqual(result['first'], seconds(r['First boarding service time']))
                self.assertEqual(result['last'], seconds(r['Last boarding service time']))
            checked += 1
        self.assertGreater(checked, 2000)


if __name__ == '__main__':
    unittest.main()
