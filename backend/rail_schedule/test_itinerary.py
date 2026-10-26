"""Semantic integration tests over the pinned feed; no network or Google key needed."""
import json
import unittest
from collections import defaultdict
from unittest.mock import patch

from backend.rail_schedule.itinerary import RailNetwork, ROOT, distance, service_seconds
from backend.rail_schedule.schedule_lookup import lookup


class ItineraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = ROOT / 'output/manifest.json'
        if not manifest.exists():
            raise unittest.SkipTest('Generate schedule exports and retain their GTFS archive first.')
        source = json.loads(manifest.read_text())
        if not (ROOT / source['local_archive']).exists():
            raise unittest.SkipTest('Matching pinned GTFS archive is required for geometry tests.')
        cls.n = RailNetwork()

    def direct(self, a='place-pktrm', b='place-asmnl', route='Red'):
        return self.n.options(a, b, '2026-10-22', route)['options'][0]['legs'][0]

    def scenario(self, legs, **kwargs):
        return {'name': 'Test route', 'date': '2026-10-22', 'time': '08:00', 'legs': legs, **kwargs}

    def foot(self, a, b):
        return {'mode': 'run', 'from': a, 'to': b, 'geometry': [self.n.stations[a]['point'], self.n.stations[b]['point']],
                'geometry_source': 'straight_line_sketch'}

    def test_geographic_paths_use_ordered_shape_vertices_not_chords(self):
        ride = self.direct('place-alfcl', 'place-pktrm')
        self.assertGreater(len(ride['geometry']), 50)
        p = self.n.patterns[ride['pattern']]
        self.assertGreater(ride['distance'], distance(ride['geometry'][0], ride['geometry'][-1]))
        self.assertTrue(all(a <= b for a, b in zip(p['positions'], p['positions'][1:])))
        for call, position in zip(p['calls'], p['positions']):
            self.assertLess(distance(self.n.stop_point(call['stop']), self.n.interpolate(p['shape'], position)), 150)

    def test_branch_and_wait_match_independent_lookup(self):
        a = self.direct()
        self.assertIn('place-shmnl', a['stations'])
        self.assertNotIn('place-brntn', a['stations'])
        b = self.direct(b='place-brntn')
        self.assertNotIn('place-shmnl', b['stations'])
        result = self.n.evaluate(self.scenario([a]))
        expected = lookup(self.n.directory, '2026-10-22', 'Red', 'place-pktrm', '0', 28800, 'Ashmont')
        self.assertEqual(result['legs'][0]['trip_id'], expected['departures'][0]['Trip ID'])
        self.assertEqual(result['legs'][0]['wait_seconds'], 480)
        self.assertEqual(result['summary']['record_proxy_seconds'], result['summary']['ride'])

    def test_cross_line_paths_are_expanded_into_actual_rides_and_transfers(self):
        path = self.n.options('place-alfcl', 'place-aport', '2026-10-22')['options'][0]
        self.assertGreaterEqual(len(path['legs']), 3)
        self.assertEqual(path['legs'][0]['route'], 'Red')
        self.assertEqual(path['legs'][-1]['route'], 'Blue')
        result = self.n.evaluate(self.scenario(path['legs']))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len([e for e in result['events'] if e['mode'] == 'transfer']), len(path['legs']) - 1)
        self.assertEqual(result['summary']['elapsed'], sum(result['summary'][m] for m in ('ride', 'wait', 'transfer', 'access', 'run', 'walk')))

    def test_connected_parent_stations_use_the_directed_passage(self):
        path = self.n.options('place-boyls', 'place-state', '2026-10-22')['options'][0]
        result = self.n.evaluate(self.scenario(path['legs']))
        self.assertEqual(result['status'], 'ok')
        # Every parent-changing transfer must be backed by a directed GTFS path/rule.
        for a, b in zip(path['legs'], path['legs'][1:]):
            self.assertIsNotNone(self.n.transfer(a['to_stop'], b['from_stop']))

    def test_transfer_minimum_is_a_floor_and_trip_restrictions_stay_specific(self):
        a, b = '70075', '70196'
        rule = {'from_trip_id': '', 'to_trip_id': '', 'transfer_type': '2', 'min_transfer_time': '120',
                'min_walk_time': '60', 'suggested_buffer_time': '10'}
        rules = defaultdict(list, {(a, b): [rule, {**rule, 'from_trip_id': 'blocked-trip', 'transfer_type': '3'}]})
        with patch.object(self.n, 'transfer_rules', rules), patch.object(self.n, 'pathway_time', return_value=(50, False)):
            self.assertEqual(self.n.transfer(a, b, 30, 'other-trip', 'target')['seconds'], 150)
            self.assertIsNone(self.n.transfer(a, b, 30, 'blocked-trip', 'target'))
        with patch.object(self.n, 'transfer_rules', rules), patch.object(self.n, 'pathway_time', return_value=None):
            self.assertIsNone(self.n.transfer(b, a))  # Never manufacture the reverse directed edge.

    def test_staying_on_one_trip_does_not_charge_another_wait_or_transfer(self):
        full = self.direct('place-alfcl', 'place-asmnl')
        p = self.n.patterns[full['pattern']]
        middle = next(i for i,c in enumerate(p['calls']) if c['station'] == 'place-pktrm')
        split = [self.n.ride(p['id'], full['start'], middle), self.n.ride(p['id'], middle, full['end'])]
        whole = self.n.evaluate(self.scenario([full]))
        result = self.n.evaluate(self.scenario(split))
        self.assertTrue(result['legs'][1]['continuous'])
        self.assertEqual(result['legs'][1]['wait_seconds'], 0)
        self.assertEqual(result['legs'][1]['transfer_seconds'], 0)
        self.assertEqual(result['summary']['elapsed'], whole['summary']['elapsed'])

    def test_earlier_foot_edit_changes_the_next_feasible_train(self):
        legs = [self.foot('place-pktrm', 'place-dwnxg'), self.direct('place-dwnxg', 'place-asmnl')]
        quick = self.n.evaluate(self.scenario(legs, time='08:05', assumptions={'run_pace': 3}))
        slow = self.n.evaluate(self.scenario(legs, time='08:05', assumptions={'run_pace': 30}))
        self.assertGreater(slow['legs'][1]['departure'], quick['legs'][1]['departure'])
        self.assertNotEqual(slow['legs'][1]['trip_id'], quick['legs'][1]['trip_id'])
        only_foot = self.n.evaluate(self.scenario(legs[:1]))
        self.assertEqual(only_foot['covered'], [])
        self.assertNotIn('place-pktrm', quick['covered'])

    def test_disconnected_edits_do_not_claim_later_coverage(self):
        legs = [self.direct(), self.direct('place-wondl', 'place-aport', 'Blue')]
        result = self.n.evaluate(self.scenario(legs))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['legs'][1]['status'], 'blocked')
        self.assertNotIn('place-wondl', result['covered'])

    def test_overnight_and_unpublished_service_dates(self):
        leg = self.direct()
        late = self.n.evaluate(self.scenario([leg], date='2026-10-23', time='25:00'))
        self.assertEqual(late['status'], 'ok')
        self.assertGreaterEqual(late['legs'][0]['departure'], 90000)
        outside = self.n.evaluate(self.scenario([leg], date='2026-12-25'))
        self.assertEqual(outside['legs'][0]['status'], 'unavailable')
        self.assertEqual(outside['covered'], [])
        self.assertEqual(self.n.options('place-pktrm', 'place-asmnl', '2026-12-25')['options'], [])

    def test_same_line_branch_changes_and_repeated_stations_are_searchable(self):
        branch = self.n.options('place-asmnl', 'place-brntn', '2026-10-22')
        self.assertTrue(branch['options'], branch['message'])
        first = branch['options'][0]
        self.assertEqual([l['route'] for l in first['legs']], ['Red', 'Red'])
        self.assertEqual(first['legs'][0]['to'], 'place-jfk')
        self.assertEqual(first['revisited_stations'], 0)
        result = self.n.evaluate(self.scenario(first['legs']))
        self.assertEqual(result['status'], 'ok')
        self.assertGreater(result['legs'][1]['transfer_seconds'], 0)
        # Riverside -> Heath Street must re-traverse trunk stations; repeated traversal is allowed and labelled.
        trunk = self.n.options('place-river', 'place-hsmnl', '2026-10-22')
        self.assertTrue(trunk['options'], trunk['message'])
        self.assertEqual(trunk['options'][0]['legs'][-1]['route'], 'Green-E')
        self.assertEqual(self.n.evaluate(self.scenario(trunk['options'][0]['legs']))['status'], 'ok')
        # A rare pattern (early trips only) must not hide the regular service on the same platforms.
        p = self.n.patterns[trunk['options'][0]['legs'][-1]['pattern']]
        rare = min((pid for pid, _, _ in self.n.equivalents(p['id'], 0, 1)), key=lambda pid: sum(len(t) for (_, q), t in self.n.scheduled.items() if q == pid), default=None)
        if rare:
            swapped = self.n.evaluate(self.scenario([self.n.ride(rare, *self.n.equivalents(p['id'], 0, 1)[0][1:])]))
            self.assertEqual(swapped['legs'][0]['status'], 'ok')
        # A plain single ride is still preferred and pointless same-line loops are not offered.
        direct = self.n.options('place-asmnl', 'place-matt', '2026-10-22')['options']
        self.assertEqual([o['label'] for o in direct], ['Mattapan'])

    def test_options_respect_the_platform_ready_time(self):
        ended = self.n.options('place-pktrm', 'place-asmnl', '2026-10-22', 'Red', '25:30')
        self.assertEqual(ended['options'], [])
        self.assertIn('has ended for 2026-10-22', ended['message'])
        self.assertTrue(self.n.options('place-pktrm', 'place-asmnl', '2026-10-22', 'Red', '08:00')['options'])

    def test_unavailable_rides_explain_why_and_keep_downstream_estimates(self):
        legs = [self.direct(), self.direct('place-asmnl', 'place-matt', 'Mattapan')]
        late = self.n.evaluate(self.scenario(legs, time='25:30'))
        self.assertEqual(late['status'], 'partial')
        self.assertEqual(late['summary']['unavailable_legs'], [1, 2])
        first, second = late['legs']
        self.assertEqual(first['reason_code'], 'no_service_remaining')
        self.assertEqual(first['last_departure'], 24 * 3600 + 46 * 60)
        self.assertIn('24:46', first['message'])
        self.assertEqual(first['time_kind'], 'estimated')
        self.assertIsNone(first['trip_id'])
        self.assertEqual(first['travel_seconds'], self.n.typical_seconds(first['pattern'], first['start'], first['end']))
        self.assertEqual(second['status'], 'unavailable')
        self.assertEqual(late['summary']['elapsed'], first['travel_seconds'] + second['travel_seconds'] + second['transfer_seconds'])
        self.assertEqual(late['summary']['estimated_ride'], first['travel_seconds'] + second['travel_seconds'])
        self.assertEqual(late['covered'], [])  # Estimates never earn planned rail coverage.
        outside = self.n.evaluate(self.scenario(legs, date='2026-12-25'))
        self.assertEqual(outside['legs'][0]['reason_code'], 'outside_feed')
        blocked = defaultdict(list, {(legs[0]['to_stop'], legs[1]['from_stop']): [
            {'from_trip_id': '', 'to_trip_id': '', 'transfer_type': '3', 'min_transfer_time': '', 'min_walk_time': '', 'suggested_buffer_time': ''}]})
        with patch.object(self.n, 'transfer_rules', blocked):
            result = self.n.evaluate(self.scenario(legs))
        self.assertEqual(result['legs'][1]['reason_code'], 'transfer_not_permitted')
        self.assertIn(legs[1]['from_stop'], result['legs'][1]['message'])

    def test_segments_carry_scheduled_or_estimated_times_per_station_pair(self):
        ride = self.direct('place-alfcl', 'place-pktrm')
        evaluated = self.n.evaluate(self.scenario([ride]))['legs'][0]
        segments = evaluated['segments']
        self.assertEqual(len(segments), len(ride['stations']) - 1)
        self.assertEqual([s['from'] for s in segments] + [segments[-1]['to']], ride['stations'])
        self.assertEqual(sum(s['seconds'] + s['dwell_seconds'] for s in segments), evaluated['travel_seconds'])
        self.assertTrue(all(s['time_kind'] == 'scheduled_estimate' and len(s['geometry']) >= 2 for s in segments))
        self.assertEqual(segments[0]['geometry'][0], ride['geometry'][0])
        self.assertEqual(segments[-1]['geometry'][-1], ride['geometry'][-1])
        typical = self.n.segments(ride['pattern'], ride['start'], ride['end'])
        self.assertTrue(all(s['time_kind'] == 'estimated' and s['seconds'] >= 60 for s in typical))

    def test_stations_without_gtfs_pathways_get_an_explicit_estimated_platform_change(self):
        inbound, outbound = sorted(s for s, r in self.n.stops.items() if r.get('parent_station') == 'place-clmnl' and r['location_type'] == '0')
        self.assertNotIn('place-clmnl', self.n.pathway_stations)
        change = self.n.transfer(inbound, outbound, 30, station_change=90)
        self.assertTrue(change['fallback'] and change['estimated'])
        self.assertEqual(change['seconds'], 120)
        # Park Street has GTFS pathways, so an unconnected platform pair there stays unavailable.
        self.assertIn('place-pktrm', self.n.pathway_stations)
        with patch.object(self.n, 'transfer_rules', defaultdict(list)), patch.object(self.n, 'pathway_time', return_value=None):
            self.assertIsNone(self.n.transfer('70196', '70075'))

    def test_invalid_geometry_modes_and_assumptions_are_rejected(self):
        for legs in ([None], [{'mode': 'drive'}], [{**self.foot('place-pktrm', 'place-dwnxg'), 'geometry': [[float('nan'),0],[0,0]]}]):
            with self.assertRaises(ValueError):
                self.n.evaluate(self.scenario(legs))
        with self.assertRaises(ValueError):
            self.n.evaluate(self.scenario([], assumptions={'run_pace': float('inf')}))
        with self.assertRaises(ValueError):
            service_seconds('08:99')
        for values in ({'dataset': 'different-feed'}, {'ruleset': 'unknown-rules'}):
            with self.assertRaises(ValueError):
                self.n.evaluate(self.scenario([], **values))

if __name__ == '__main__':
    unittest.main()
