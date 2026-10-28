"""Backtracking analysis for an itinerary, speedrun style.

A *backtrack* is any station-to-station piece the plan rides (or runs) again after it has already been traversed in
either direction. Consecutive repeated pieces form a *stretch* from the station where new ground stopped (A) to the
station where it resumes (B); for every stretch the shortcut search asks how else A → B could be connected — a
scheduled bus or Silver ride, another rail path, or a run — and reports the time each would save. Shortcut times
come from the same evaluator with the scenario's own assumptions (real timetable, waits included); runs are
straight-line estimates until a street route is previewed. Unavailable or blocked legs are not traversed track. Nothing here changes coverage rules: buses and runs stay connectors.
"""
import math

from .itinerary import clock, distance

RUN_DETOUR = 1.25  # Straight-line → street distance factor for the run estimate; previewing fetches the real route.
MAX_RUN_METERS = 3500
MAX_SUGGESTIONS = 3
MIN_SHORTCUT_SECONDS = 240


def edge(a, b):
    return frozenset((a, b))


def stamp(seconds):
    """Exact service time HH:MM:SS so a shortcut is never allowed to board before it actually arrives."""
    seconds = max(0, int(math.ceil(seconds)))
    return f'{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}'


def pieces(result):
    """Flatten evaluated legs into ordered traversed pieces with timing, marking repeats of an already-ridden edge."""
    seen, out = set(), []
    for i, leg in enumerate(result['legs']):
        if leg['status'] != 'ok':
            # Not actually ridden: no traversed track, but the gap must still separate the repeats on either side.
            out.append({'leg': i, 'segment': None, 'from': leg['from'], 'to': leg['to'], 'kind': 'gap', 'seconds': 0,
                        'departure': None, 'arrival': None, 'time_kind': 'estimated', 'repeated': False, 'gap': True})
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
                        'arrival': leg.get('arrival'),
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
            if piece['repeated'] or piece.get('gap') or piece['kind'] not in ('rail', 'silver'):
                break
            follow.append(piece)
        if follow and follow[-1]['to'] not in (s['start'], s['end']) and follow[-1]['arrival'] is not None:
            s['reverse'] = {'target': follow[-1]['to'], 'arrives': follow[-1]['arrival'], 'legs': sorted({p['leg'] + 1 for p in follow})}
        s['ride_seconds'] = sum(flat[i]['seconds'] for i in s['pieces'])
        leaves, arrives = first['departure'], last['arrival']
        if leaves is None:  # Estimated ride: fall back to the previous piece's arrival or the leg's start.
            before = flat[s['pieces'][0] - 1] if s['pieces'][0] else None
            leaves = (before or {}).get('arrival') or result['legs'][first['leg']].get('start_time')
        if leaves is None or arrives is None:
            s['leaves'] = s['arrives'] = None
            s['elapsed_seconds'] = s['ride_seconds']
            s['stations'] = [first['from']] + [flat[i]['to'] for i in s['pieces']]
            s['estimated'] = True
            s['legs'] = [l + 1 for l in s['legs']]
            continue
        s['leaves'] = leaves
        s['arrives'] = arrives
        s['elapsed_seconds'] = (arrives - leaves) if leaves is not None and arrives is not None else s['ride_seconds']
        s['stations'] = [first['from']] + [flat[i]['to'] for i in s['pieces']]
        s['estimated'] = any(flat[i]['time_kind'] != 'scheduled_estimate' for i in s['pieces'])
        s['legs'] = [l + 1 for l in s['legs']]  # 1-based for display
    return out


def shortcuts(network, stretch, day, assumptions):
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
            found.extend(candidates(network, stretch, target, budget, rev, day, assumptions))
    found = [f for f in found if f['saves_seconds'] > 0]
    found.sort(key=lambda f: -f['saves_seconds'])
    return found[:MAX_SUGGESTIONS]


def evaluated(network, option, day, ready, assumptions, kind, legs=None):
    """Time an alternative with the scenario's own assumptions from an exact service time; None when infeasible.

    `legs` may chain extra legs after the option (e.g. the reverse ride) so transfers between them are priced.
    """
    legs = legs if legs is not None else option['legs']
    try:
        res = network.evaluate({'date': day, 'time': stamp(ready), 'legs': legs, 'assumptions': assumptions})
    except ValueError:
        return None
    if res['status'] != 'ok':
        return None
    done = res['legs']
    return {'kind': kind, 'label': option['label'], 'legs': option['legs'], 'seconds': res['summary']['elapsed'],
            'departure': done[0].get('departure'), 'arrival': done[-1].get('arrival'), 'evaluated_legs': done,
            'wait_seconds': sum(l.get('wait_seconds', 0) + l.get('transfer_seconds', 0) for l in done),
            'time_kind': 'scheduled_estimate', 'via': [network.stations[l['to']]['name'] for l in option['legs'][:-1]]}


def reverse_ride(network, item, c, b, leaves, day, assumptions):
    """An actual C → B rail/Silver path boardable after the shortcut reaches C, with the connection priced.

    Bus/rail shortcuts are chained in front of the reverse ride so the evaluator charges the real transfer (bus stop →
    platform walk, buffer); a run arrives outdoors, so the scenario's station access time applies before boarding.
    """
    if item['kind'] == 'run':
        ready = leaves + item['seconds'] + float(assumptions.get('access', 60))
    else:
        ready = item['arrival']
    try:
        options = network.options(c, b, day, '', stamp(ready), mode='rail')['options']
    except ValueError:
        return None
    best = None
    for option in options[:3]:
        if item['kind'] == 'run':
            back = evaluated(network, option, day, ready, assumptions, 'ride')
            if back:
                back['transfer_seconds'] = float(assumptions.get('access', 60))
        else:
            chained = evaluated(network, option, day, leaves, assumptions, 'ride', legs=item['legs'] + option['legs'])
            if not chained:
                continue
            mine = chained['evaluated_legs'][len(item['legs']):]
            back = {'label': option['label'], 'departure': mine[0]['departure'], 'arrival': mine[-1]['arrival'],
                    'seconds': mine[-1]['arrival'] - item['arrival'], 'transfer_seconds': mine[0].get('transfer_seconds', 0),
                    'wait_seconds': sum(l.get('wait_seconds', 0) + l.get('transfer_seconds', 0) for l in mine)}
        if back and (best is None or back['seconds'] < best['seconds']):
            best = back
    return best


def candidates(network, stretch, b, budget, reverse, day, assumptions):
    a, leaves = stretch['start'], stretch['leaves']
    run_pace = float(assumptions.get('run_pace', 6))
    ready = stamp(leaves)
    ridden = {edge(x, y) for x, y in zip(stretch['stations'], stretch['stations'][1:])}
    found = []

    timed = lambda option, kind: evaluated(network, option, day, leaves, assumptions, kind)
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
    priced = []
    for item in found:
        item.pop('evaluated_legs', None)
        item['target'] = b
        item['saves_seconds'] = budget - item['seconds']
        if reverse:
            # Riding C → B backwards needs a real train after the shortcut arrives; the forward duration is not reused.
            back = reverse_ride(network, item, b, stretch['end'], leaves, day, assumptions)
            if not back:
                continue
            item['then'] = {'from': b, 'to': stretch['end'], 'seconds': back['seconds'], 'label': back['label'],
                            'departure': back['departure'], 'arrival': back['arrival'], 'wait_seconds': back['wait_seconds'],
                            'transfer_seconds': back['transfer_seconds'], 'replaces_legs': reverse['legs']}
            item['saves_seconds'] -= back['seconds']
        priced.append(item)
    return priced


def analyze(network, scenario):
    result = network.evaluate(scenario)
    flat = pieces(result)
    runs = stretches(flat, result)
    assumptions = scenario.get('assumptions') or {}  # Already validated by evaluate(); shortcuts must use the same costs.
    for s in runs:
        # Shortcut search evaluates several alternatives per stretch; very short repeats (a station or two) are not worth it.
        s['shortcuts'] = shortcuts(network, s, str(scenario.get('date', '')), assumptions) if s['elapsed_seconds'] >= MIN_SHORTCUT_SECONDS else []
        s['best_saving_seconds'] = s['shortcuts'][0]['saves_seconds'] if s['shortcuts'] else 0
    ridden = [p for p in flat if not p.get('gap')]
    moving = sum(p['seconds'] for p in ridden)
    repeated = sum(p['seconds'] for p in ridden if p['repeated'])
    visits = {}
    for p in ridden:
        visits[p['to']] = visits.get(p['to'], 0) + 1
    if ridden:
        visits[ridden[0]['from']] = visits.get(ridden[0]['from'], 0) + 1
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
