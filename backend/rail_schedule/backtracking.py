"""Backtracking analysis for an itinerary, speedrun style.

A *backtrack* is any station-to-station piece the plan rides (or runs) again after it has already been traversed in
either direction. Consecutive repeated pieces form a *stretch* from the station where new ground stopped (A) to the
station where it resumes (B); for every stretch the shortcut search asks how else A → B could be connected — a
scheduled bus or Silver ride, another rail path, or a run — and reports the time each would save. Shortcut times
come from the same evaluator (real timetable, waits included); runs are straight-line estimates until a street
route is previewed. Nothing here changes coverage rules: buses and runs stay connectors.
"""
import math

from .itinerary import clock, distance

RUN_DETOUR = 1.25  # Straight-line → street distance factor for the run estimate; previewing fetches the real route.
MAX_RUN_METERS = 3500
MAX_SUGGESTIONS = 3


def edge(a, b):
    return frozenset((a, b))


def pieces(result):
    """Flatten evaluated legs into ordered traversed pieces with timing, marking repeats of an already-ridden edge."""
    seen, out = set(), []
    for i, leg in enumerate(result['legs']):
        if leg['status'] == 'blocked':
            continue
        if leg['mode'] == 'ride' and leg.get('segments'):
            for k, s in enumerate(leg['segments']):
                e = edge(s['from'], s['to'])
                out.append({'leg': i, 'segment': k, 'from': s['from'], 'to': s['to'], 'kind': leg['kind'],
                            'seconds': s.get('seconds') or 0, 'departure': s.get('departure'), 'arrival': s.get('arrival'),
                            'time_kind': s.get('time_kind', 'estimated'), 'repeated': e in seen and s['from'] != s['to']})
                seen.add(e)
        else:
            e = edge(leg['from'], leg['to'])
            out.append({'leg': i, 'segment': None, 'from': leg['from'], 'to': leg['to'], 'kind': leg.get('kind') or leg['mode'],
                        'seconds': leg.get('travel_seconds') or 0, 'departure': leg.get('departure'),
                        'arrival': leg.get('arrival') if leg['status'] == 'ok' else leg.get('estimated_arrival'),
                        'time_kind': leg.get('time_kind', 'estimated'), 'repeated': e in seen})
            seen.add(e)
    return out


def stretches(flat, result):
    """Group consecutive repeated pieces; elapsed time runs from leaving A to arriving at B, waits/transfers included."""
    out, current = [], None
    for index, piece in enumerate(flat):
        if piece['repeated']:
            if current is None:
                current = {'start': piece['from'], 'pieces': [], 'legs': []}
            current['pieces'].append(index)
            if piece['leg'] not in current['legs']:
                current['legs'].append(piece['leg'])
        elif current is not None:
            out.append(current)
            current = None
    if current is not None:
        out.append(current)
    for s in out:
        first, last = flat[s['pieces'][0]], flat[s['pieces'][-1]]
        s['end'] = last['to']
        # New ground that immediately follows the stretch: a shortcut may instead jump to its far end and ride it in reverse.
        follow = []
        for piece in flat[s['pieces'][-1] + 1:]:
            if piece['repeated'] or piece['kind'] not in ('rail', 'silver'):
                break
            follow.append(piece)
        if follow and follow[-1]['to'] not in (s['start'], s['end']) and follow[-1]['arrival'] is not None:
            s['reverse'] = {'target': follow[-1]['to'], 'seconds': sum(p['seconds'] for p in follow), 'arrives': follow[-1]['arrival'],
                            'legs': sorted({p['leg'] + 1 for p in follow})}
        s['ride_seconds'] = sum(flat[i]['seconds'] for i in s['pieces'])
        leaves = first['departure']
        if leaves is None:  # Estimated ride: fall back to the previous piece's arrival or the leg's start.
            before = flat[s['pieces'][0] - 1] if s['pieces'][0] else None
            leaves = (before or {}).get('arrival') or result['legs'][first['leg']].get('start_time')
        arrives = last['arrival']
        s['leaves'] = leaves
        s['arrives'] = arrives
        s['elapsed_seconds'] = (arrives - leaves) if leaves is not None and arrives is not None else s['ride_seconds']
        s['stations'] = [first['from']] + [flat[i]['to'] for i in s['pieces']]
        s['estimated'] = any(flat[i]['time_kind'] != 'scheduled_estimate' for i in s['pieces'])
        s['legs'] = [l + 1 for l in s['legs']]  # 1-based for display
    return out


def shortcuts(network, stretch, day, run_pace):
    """Alternatives for A → B (and A → C with the following new ground ridden in reverse), each timed from the moment
    the plan leaves A. Only faster ones are returned."""
    a, leaves = stretch['start'], stretch['leaves']
    if leaves is None:
        return []
    targets = [(stretch['end'], stretch['elapsed_seconds'], None)]
    reverse = stretch.get('reverse')
    if reverse:
        # Reaching C directly, then riding C → B backwards, replaces the stretch plus the following new ground.
        targets.append((reverse['target'], reverse['arrives'] - leaves, reverse))
    found = []
    for target, budget, rev in targets:
        if target != a:
            found.extend(candidates(network, stretch, target, budget, rev, day, run_pace))
    found = [f for f in found if f['saves_seconds'] > 0]
    found.sort(key=lambda f: -f['saves_seconds'])
    return found[:MAX_SUGGESTIONS]


def candidates(network, stretch, b, budget, reverse, day, run_pace):
    a, leaves = stretch['start'], stretch['leaves']
    ready = clock(max(0, leaves))
    ridden = {edge(x, y) for x, y in zip(stretch['stations'], stretch['stations'][1:])}
    found = []

    def timed(option, kind):
        try:
            res = network.evaluate({'date': day, 'time': ready, 'legs': option['legs']})
        except ValueError:
            return None
        if res['status'] != 'ok':
            return None
        legs = res['legs']
        return {'kind': kind, 'label': option['label'], 'legs': option['legs'], 'seconds': res['summary']['elapsed'],
                'departure': legs[0].get('departure'), 'arrival': legs[-1].get('arrival'),
                'wait_seconds': sum(l.get('wait_seconds', 0) + l.get('transfer_seconds', 0) for l in legs),
                'time_kind': 'scheduled_estimate', 'via': [network.stations[l['to']]['name'] for l in option['legs'][:-1]]}

    for mode, kind in (('rail', 'ride'), ('bus', 'bus')):
        try:
            options = network.options(a, b, day, '', ready, mode=mode)['options']
        except ValueError:
            options = []
        for option in options[:2]:
            edges = {edge(x, y) for l in option['legs'] for x, y in zip(l['stations'], l['stations'][1:])}
            if mode == 'rail' and edges <= ridden:
                continue  # That is the backtrack itself, not a shortcut.
            item = timed(option, 'silver' if all(l['kind'] == 'silver' for l in option['legs']) else kind)
            if item:
                found.append(item)
    meters = distance(network.stations[a]['point'], network.stations[b]['point']) * RUN_DETOUR
    if meters <= MAX_RUN_METERS:
        seconds = math.ceil(meters / 1000 * run_pace * 60)
        found.append({'kind': 'run', 'label': f'Run {meters / 1000:.1f} km', 'seconds': seconds, 'meters': round(meters),
                      'time_kind': 'estimated', 'wait_seconds': 0, 'via': [],
                      'note': f'straight-line ×{RUN_DETOUR} estimate at {run_pace:g} min/km; preview Run for the street route'})
    for item in found:
        item['target'] = b
        item['saves_seconds'] = budget - item['seconds']
        if reverse:
            item['then'] = {'from': b, 'to': stretch['end'], 'seconds': reverse['seconds'], 'legs': reverse['legs']}
            item['saves_seconds'] -= reverse['seconds']
    return found


def analyze(network, scenario):
    result = network.evaluate(scenario)
    flat = pieces(result)
    runs = stretches(flat, result)
    run_pace = float((scenario.get('assumptions') or {}).get('run_pace', 6))
    for s in runs:
        s['shortcuts'] = shortcuts(network, s, str(scenario.get('date', '')), run_pace)
        s['best_saving_seconds'] = s['shortcuts'][0]['saves_seconds'] if s['shortcuts'] else 0
    moving = sum(p['seconds'] for p in flat)
    repeated = sum(p['seconds'] for p in flat if p['repeated'])
    visits = {}
    for p in flat:
        visits[p['to']] = visits.get(p['to'], 0) + 1
    if flat:
        visits[flat[0]['from']] = visits.get(flat[0]['from'], 0) + 1
    return {'moving_seconds': moving, 'backtrack_seconds': repeated,
            'backtrack_share': round(repeated / moving, 3) if moving else 0,
            'repeated_pieces': [{'leg': p['leg'], 'segment': p['segment']} for p in flat if p['repeated']],
            'repeated_station_visits': sum(v - 1 for v in visits.values() if v > 1),
            'stretches': [{k: v for k, v in s.items() if k != 'pieces'} for s in runs],
            'potential_saving_seconds': sum(s['best_saving_seconds'] for s in runs),
            'definition': 'Backtracking = any station-to-station piece ridden or run again after it was already traversed in either direction. '
                          'Stretches run from where new ground stopped to where it resumes; shortcut times use the same timetable evaluator '
                          '(waits included), runs are straight-line estimates until previewed.',
            'dataset': result['dataset']}
