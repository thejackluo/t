#!/usr/bin/env python3
"""Look up the next scheduled boardable core-rail departure, using workbook CSVs."""
import argparse
import csv
import gzip
import json
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__:
    from .paths import OUTPUT_DIR
else:
    from paths import OUTPUT_DIR


def rows(directory, name):
    with gzip.open(directory / (name + '.csv.gz'), 'rt', newline='', encoding='utf-8') as f:
        yield from csv.DictReader(f)


def service_seconds(value):
    if not re.fullmatch(r'\d{2,}:[0-5]\d:[0-5]\d', value):
        raise argparse.ArgumentTypeError('Use service HH:MM:SS, e.g. 08:00:00 or 25:15:00')
    h, m, s = map(int, value.split(':'))
    return h * 3600 + m * 60 + s


def lookup(directory, day, route, station, direction, arrival, destination=None, stop=None):
    calendar = next((r for r in rows(directory, 'service_calendar') if r['Service date'] == day and r['Route'] == route), None)
    if calendar is None:
        return {'status': 'Date/route outside published coverage', 'service_date': day, 'route': route}
    pid = calendar['Profile ID']
    matches = []
    for r in rows(directory, 'departures'):
        if (r['Profile ID'] == pid and r['Station ID'] == station and r['Direction ID'] == str(direction)
                and r['Can board'] == '1' and int(r['Departure service seconds']) >= arrival
                and (not destination or r['Destination'] == destination)
                and (not stop or r['Platform stop ID'] == stop)):
            matches.append(r)
    result = {'kind': 'scheduled_estimate', 'service_date': day, 'route': route, 'station_id': station,
              'direction_id': str(direction), 'requested_destination': destination, 'profile_id': pid,
              'holiday': calendar['Holiday name'], 'arrival_service_seconds': arrival}
    if not matches:
        result['status'] = 'No further matching boardable departures on this service day'
        return result
    earliest = min(int(r['Departure service seconds']) for r in matches)
    matches = [r for r in matches if int(r['Departure service seconds']) == earliest]
    # GTFS service origin: local noon minus 12 elapsed hours, not naive local midnight.
    local_noon = datetime.combine(date.fromisoformat(day), datetime.min.time().replace(hour=12), ZoneInfo('America/New_York'))
    next_time = datetime.fromtimestamp(local_noon.timestamp() - 43200 + earliest, ZoneInfo('America/New_York'))
    result.update({'status': 'Found', 'scheduled_wait_seconds': earliest - arrival,
                   'scheduled_wait_minutes': (earliest-arrival)/60,
                   'next_departure_service_time': matches[0]['Departure service time'],
                   'next_departure_local_iso': next_time.isoformat(),
                   'departures': matches})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, default=OUTPUT_DIR)
    p.add_argument('--date', required=True, help='Service date YYYY-MM-DD')
    p.add_argument('--time', required=True, type=service_seconds, help='Platform-arrival service HH:MM:SS (24+ allowed)')
    p.add_argument('--route', required=True)
    p.add_argument('--station', required=True, help='Parent station ID, e.g. place-pktrm')
    p.add_argument('--direction', required=True, choices=['0', '1'])
    p.add_argument('--destination', help='Exact headsign, e.g. Ashmont')
    p.add_argument('--stop', help='Optional exact platform stop ID')
    args = p.parse_args()
    date.fromisoformat(args.date)
    print(json.dumps(lookup(args.data, args.date, args.route, args.station, args.direction,
                            args.time, args.destination, args.stop), indent=2))


if __name__ == '__main__':
    main()
