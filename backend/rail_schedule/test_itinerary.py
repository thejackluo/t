"""Semantic integration tests over the pinned feed; no network or Google key needed."""
import json
import math
import unittest
from collections import defaultdict
from unittest.mock import patch

from backend.rail_schedule.itinerary import COLORS, RailNetwork, ROOT, distance, service_seconds
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
        options = self.n.options('place-alfcl', 'place-aport', '2026-10-22')['options']
        self.assertEqual(options[0]['legs'][0]['route'], 'Red')
        self.assertIn(options[0]['legs'][-1]['route'], ('Blue', '743'))  # SL3 from South Station is a legitimate 2-leg path.
        path = next(o for o in options if all(leg['kind'] == 'rail' for leg in o['legs']))
        self.assertGreaterEqual(len(path['legs']), 3)
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
            blocked = self.n.transfer(a, b, 30, 'blocked-trip', 'target')
            self.assertTrue(blocked['street_level'] and blocked['fallback'])  # Priced as a re-entry, never as the forbidden edge.
            with patch.object(self.n, 'entrances', defaultdict(list)):
                self.assertIsNone(self.n.transfer(a, b, 30, 'blocked-trip', 'target'))
        with patch.object(self.n, 'transfer_rules', rules), patch.object(self.n, 'pathway_time', return_value=None):
            reverse = self.n.transfer(b, a)  # Never manufacture the reverse directed edge; only a labelled street re-entry.
            self.assertTrue(reverse['street_level'] and reverse['fallback'])

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
            priced = self.n.evaluate(self.scenario(legs))
            self.assertTrue(priced['legs'][1]['transfer']['street_level'])  # Forbidden in-station change priced as a re-entry.
            with patch.object(self.n, 'entrances', defaultdict(list)):
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
        # Park Street has GTFS pathways: an unconnected platform pair there only gets a labelled street-level re-entry,
        # and nothing at all once no entrance is reachable.
        self.assertIn('place-pktrm', self.n.pathway_stations)
        with patch.object(self.n, 'transfer_rules', defaultdict(list)), patch.object(self.n, 'pathway_time', return_value=None):
            self.assertTrue(self.n.transfer('70196', '70075')['street_level'])
            with patch.object(self.n, 'pathways', defaultdict(list)):
                self.assertIsNone(self.n.transfer('70196', '70075'))

    def test_forbidden_in_station_transfer_becomes_an_estimated_street_level_re_entry(self):
        # GTFS transfer_type 3 at Copley: westbound and eastbound platforms are only linked by crossing Boylston Street.
        change = self.n.transfer('70154', '70155', 30)
        self.assertTrue(change['street_level'] and change['estimated'] and change['fallback'])
        self.assertEqual(change['via'], ['door-coecl-bpl', 'door-coecl-church'])
        self.assertGreater(change['walk_seconds'], 2 * 44)  # Both GTFS stair pathways plus the outdoor walk.
        self.assertEqual(change['seconds'], change['walk_seconds'] + 30)
        self.assertIn('street-level', change['source'])
        with patch.object(self.n, 'entrances', defaultdict(list)):
            self.assertIsNone(self.n.transfer('70154', '70155', 30))
        # Reversing direction at Copley is now searchable and timed, labelled as a street transfer.
        found = self.n.options('place-lake', 'place-hsmnl', '2026-10-22')['options']
        self.assertTrue(any(o['street_transfers'] and o['legs'][0]['to'] == 'place-coecl' for o in found))
        to_copley = self.n.options('place-lake', 'place-coecl', '2026-10-22', 'Green-B')['options'][0]['legs']
        onward = self.n.options('place-coecl', 'place-hsmnl', '2026-10-22', 'Green-E')['options'][0]['legs']
        legs = self.n.evaluate(self.scenario(to_copley + onward))['legs']
        self.assertEqual([l['status'] for l in legs], ['ok', 'ok'])
        self.assertTrue(legs[1]['transfer']['street_level'])
        self.assertGreaterEqual(legs[1]['departure'], legs[0]['arrival'] + legs[1]['transfer']['seconds'])

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


class SilverLineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n = RailNetwork()

    def test_silver_rides_are_scheduled_and_counted_separately_from_rail(self):
        self.assertEqual(len(self.n.rail_stations), 125)
        self.assertEqual(self.n.stations['place-chels']['kind'], 'silver')
        self.assertEqual(self.n.stations['silver-terminal-a']['kind'], 'silver')
        self.assertEqual(self.n.parent('17091'), 'silver-terminal-a')
        option = self.n.options('place-sstat', 'place-chels', '2026-10-22', '743')['options'][0]
        leg = option['legs'][0]
        self.assertEqual((leg['route'], leg['route_name'], leg['kind']), ('743', 'SL3', 'silver'))
        self.assertEqual(leg['stations'][:2], ['place-sstat', 'place-crtst'])
        result = self.n.evaluate({'date': '2026-10-22', 'time': '08:00', 'legs': [leg]})
        self.assertEqual(result['legs'][0]['status'], 'ok')
        self.assertEqual(result['legs'][0]['time_kind'], 'scheduled_estimate')
        self.assertIn('place-chels', result['silver_covered'])
        self.assertNotIn('place-chels', result['covered'])
        self.assertEqual(result['covered'], ['place-aport', 'place-sstat'])
        self.assertEqual(len(result['missing']) + len(result['covered']), 125)
        self.assertEqual(len(result['silver_missing']) + len(result['silver_covered']), len(self.n.stations) - 125)
        meta = self.n.metadata()
        self.assertEqual(meta['rail_station_count'], 125)
        self.assertIn({'id': '743', 'name': 'SL3', 'color': '#7C878E', 'kind': 'silver'}, meta['routes'])

    def test_rail_only_filter_still_excludes_silver(self):
        for option in self.n.options('place-sstat', 'place-aport', '2026-10-22', 'Red')['options']:
            self.assertTrue(all(leg['kind'] == 'rail' for leg in option['legs']))


class BusConnectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n = RailNetwork()

    def test_direct_buses_are_scheduled_connectors_that_never_earn_coverage(self):
        self.assertTrue(self.n.bus['routes'])
        self.assertNotIn('741', self.n.bus['routes'])  # Silver is its own kind, shuttles are excluded.
        self.assertFalse(any(r.startswith('Shuttle') for r in self.n.bus['routes']))
        bus = self.n.options('place-forhl', 'place-asmnl', '2026-10-22', '', '08:00', mode='bus')['options'][0]['legs'][0]
        self.assertEqual((bus['route'], bus['kind'], bus['from'], bus['to']), ('21', 'bus', 'place-forhl', 'place-asmnl'))
        self.assertIn(bus['from_stop'], self.n.bus_stops)
        rail = self.n.options('place-rugg', 'place-forhl', '2026-10-22', 'Orange', '08:00')['options'][0]['legs']
        red = self.n.options('place-asmnl', 'place-jfk', '2026-10-22', 'Red', '09:00')['options'][0]['legs']
        result = self.n.evaluate({'date': '2026-10-22', 'time': '08:00', 'legs': rail + [bus] + red})
        self.assertEqual(result['status'], 'ok')
        legs = result['legs']
        self.assertEqual([l['kind'] for l in legs], ['rail', 'bus', 'rail'])
        self.assertEqual(legs[1]['time_kind'], 'scheduled_estimate')
        self.assertGreaterEqual(legs[1]['departure'], legs[0]['arrival'] + legs[1]['transfer_seconds'])
        self.assertEqual(result['summary']['bus'], legs[1]['travel_seconds'])
        intermediate = set(bus['stations']) - {'place-forhl', 'place-asmnl'}
        self.assertFalse(intermediate & set(result['covered']))
        self.assertIn('place-forhl', result['covered'])
        self.assertIn('place-asmnl', result['covered'])  # Reached by rail legs, not by the bus.

    def test_rail_search_ignores_buses_and_bus_search_is_direct_only(self):
        for option in self.n.options('place-harsq', 'place-nubn', '2026-10-22', '', '09:00')['options']:
            self.assertTrue(all(leg['kind'] != 'bus' for leg in option['legs']))
        buses = self.n.options('place-harsq', 'place-nubn', '2026-10-22', '', '09:00', mode='bus')['options']
        self.assertTrue(buses and all(len(o['legs']) == 1 and o['legs'][0]['kind'] == 'bus' for o in buses))
        self.assertEqual(buses[0]['label'], '1')
        none = self.n.options('place-alfcl', 'place-wondl', '2026-10-22', '', '09:00', mode='bus')
        self.assertEqual(none['options'], [])
        self.assertIn('No direct scheduled MBTA bus', none['message'])
        with self.assertRaises(ValueError):
            self.n.options('place-harsq', 'place-nubn', '2026-10-22', '', '09:00', mode='taxi')

    def test_bus_stop_walks_are_estimated_when_gtfs_publishes_no_transfer(self):
        stop = next(s for s, r in self.n.bus_stops.items() if r['Source'] == 'proximity' and r['Station ID'] == 'place-harsq')
        walk = self.n.bus_transfer('70068', stop, 30)
        self.assertTrue(walk['estimated'] and walk['street_level'])
        self.assertEqual(walk['bus_stop'], stop)
        self.assertGreater(walk['seconds'], 30)
        self.assertIn('no GTFS transfer published', walk['source'])
        meta = self.n.metadata()
        self.assertTrue(all(l['route'] in COLORS for l in meta['lines']))  # Base map shows rail/Silver tracks only.
        self.assertIn('1', {r['id'] for r in meta['bus']['routes']})


class BacktrackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n = RailNetwork()

    def legs(self, a, b, route, time):
        return self.n.options(a, b, '2026-10-22', route, time)['options'][0]['legs']

    def test_single_ride_has_no_backtracking(self):
        from backend.rail_schedule.backtracking import analyze
        report = analyze(self.n, {'date': '2026-10-22', 'time': '08:00', 'legs': self.legs('place-alfcl', 'place-brntn', 'Red', '08:00')})
        self.assertEqual((report['backtrack_seconds'], report['stretches'], report['repeated_pieces']), (0, [], []))
        self.assertGreater(report['moving_seconds'], 0)

    def test_repeated_track_forms_stretches_with_shortcuts(self):
        from backend.rail_schedule.backtracking import analyze
        legs = (self.legs('place-alfcl', 'place-jfk', 'Red', '07:00') + self.legs('place-jfk', 'place-ogmnl', '', '07:40')
                + self.legs('place-ogmnl', 'place-forhl', 'Orange', '08:30') + self.legs('place-forhl', 'place-asmnl', '', '09:30'))
        report = analyze(self.n, {'date': '2026-10-22', 'time': '07:00', 'legs': legs})
        self.assertGreater(report['backtrack_share'], 0.3)
        self.assertEqual(report['backtrack_seconds'], sum(s['ride_seconds'] for s in report['stretches']))
        self.assertTrue(all('leg' in p and 'segment' in p for p in report['repeated_pieces']))
        last = report['stretches'][-1]
        self.assertEqual((last['start'], last['end']), ('place-forhl', 'place-jfk'))  # Orange back to the trunk, Red back to JFK.
        self.assertEqual(last['reverse']['target'], 'place-asmnl')  # JFK → Ashmont is new ground that can be ridden backwards.
        bus = next(x for x in last['shortcuts'] if x['kind'] == 'bus')
        self.assertEqual((bus['label'], bus['target'], bus['then']['from'], bus['then']['to']), ('21', 'place-asmnl', 'place-asmnl', 'place-jfk'))
        self.assertGreater(bus['saves_seconds'], 0)
        self.assertEqual(bus['seconds'] + bus['then']['seconds'] + bus['saves_seconds'], last['reverse']['arrives'] - last['leaves'])
        self.assertGreaterEqual(bus['then']['departure'], last['leaves'] + bus['seconds'])  # A real reverse train after the bus arrives.
        from backend.rail_schedule.backtracking import evaluated
        two_rides = self.n.options('place-forhl', 'place-asmnl', '2026-10-22', '', '09:30')['options'][0]
        quick = evaluated(self.n, two_rides, '2026-10-22', 34200, {}, 'ride')
        slow = evaluated(self.n, two_rides, '2026-10-22', 34200, {'buffer': 1800}, 'ride')
        # Shortcuts are priced with the scenario's own transfer buffer: a 30-minute buffer forces a later connecting train.
        self.assertGreater(slow['wait_seconds'], quick['wait_seconds'])
        self.assertGreaterEqual(slow['seconds'] - quick['seconds'], 600)

    def test_unavailable_rides_are_not_traversed_track(self):
        from backend.rail_schedule.backtracking import analyze
        legs = self.legs('place-alfcl', 'place-brntn', 'Red', '08:00') + self.legs('place-brntn', 'place-alfcl', 'Red', '09:30')
        report = analyze(self.n, {'date': '2026-10-22', 'time': '25:30', 'legs': legs})  # Service has ended: both rides unavailable.
        self.assertEqual((report['moving_seconds'], report['backtrack_seconds'], report['stretches']), (0, 0, []))
        self.assertEqual(report['potential_saving_seconds'], sum(s['best_saving_seconds'] for s in report['stretches']))

    def test_run_shortcut_is_a_labelled_straight_line_estimate(self):
        from backend.rail_schedule.backtracking import analyze, RUN_DETOUR
        legs = (self.legs('place-alfcl', 'place-pktrm', 'Red', '08:00') + self.legs('place-pktrm', 'place-mdftf', 'Green-E', '08:30')
                + self.legs('place-mdftf', 'place-pktrm', 'Green-E', '09:00') + self.legs('place-pktrm', 'place-alfcl', 'Red', '09:30'))
        report = analyze(self.n, {'date': '2026-10-22', 'time': '08:00', 'legs': legs, 'assumptions': {'run_pace': 5}})
        stretch = report['stretches'][0]
        self.assertEqual((stretch['start'], stretch['end'], stretch['legs']), ('place-mdftf', 'place-alfcl', [3, 4]))
        run = next(x for x in stretch['shortcuts'] if x['kind'] == 'run')
        meters = distance(self.n.stations['place-mdftf']['point'], self.n.stations['place-alfcl']['point']) * RUN_DETOUR
        self.assertEqual(run['meters'], round(meters))
        self.assertEqual(run['seconds'], math.ceil(meters / 1000 * 5 * 60))
        self.assertEqual(run['time_kind'], 'estimated')
        self.assertIn('straight-line', run['note'])
