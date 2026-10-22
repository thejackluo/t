# Interactive rail schedule explorer

**Use the explorer first to understand the data; use Excel alongside it for sharing, auditing, and custom calculations.** The application reads the same validated CSV snapshot generated with the workbook, rather than parsing Excel cells.

**Status:** available now. The [backend](../../backend/rail_schedule/PLAN.md#delivery-plan) and [map editor](../../frontend/map_editor/PLAN.md) have separate delivery plans; this utility helps inspect their schedule inputs.

## Start

```sh
python3 -m utilities.schedule_explorer.explore
```

Open **http://127.0.0.1:8000**. Run the command from the repository root. Python 3.9+ is sufficient; the explorer has no third-party dependencies and makes no external API requests. It loads the existing exports in the repository-level `output/`. If these are missing, generate them with `python3 -m backend.rail_schedule.build_schedule`; see [the backend guide](../../backend/rail_schedule/README.md).

Use `python3 -m utilities.schedule_explorer.explore --port 8001` for a different local port or `--data /path/to/exports` for a different generated snapshot. The server binds to the local machine by default. It can also be launched by absolute script path from another working directory; default data and static assets resolve from file locations, not that working directory.

## Explore

- Choose Red, Mattapan, Orange, Blue, or Green B/C/D/E, then search its stations.
- Select a service date, direction, and destination. First/last train cards count only boardable departures.
- Click an hourly bar to inspect that part of the timetable. Departure rows retain platform IDs, trip IDs, and gaps between usable trains.
- Enter your platform-arrival time to calculate the next matching scheduled train and wait. `25:15:00` means 1:15 AM after the selected service date.
- **Compare days** shows all published dates and route-specific service descriptions, with holiday/weekend filters. Click a date to explore its trains.
- **All stations** compares every station on the selected line/date/direction, across all destinations.
- Copy the view URL, export selected departures as CSV, or download the complete Excel workbook.
- **About the data** explains source version, coverage, time conventions, and scheduling limitations.

## Data semantics

The loaded snapshot covers **October 14–December 12, 2026**, with 125 distinct rail parent stations. Silver Line and replacement buses are excluded from this scheduling view; Silver Line support for the full attempt is separate later work.

These are **scheduled estimates**, not live predictions or actual observations. A typical gap is a median, not your personal wait. Walking and transfer readiness are not calculated automatically. Destination filters matter on branched routes. Terminal arrival-only calls never become boarding opportunities. Unpublished dates show a coverage notice and no invented timetable.

The time display shows a **+1 day** badge for after-midnight service; exports retain the original `24+` service hours. All local labels refer to America/New_York. The server loads a fixed snapshot at startup: rebuild the schedule and restart the server to adopt updated data.

## Files and checks

- `explore.py`: standard-library local server, data indexing, and read-only JSON endpoints.
- `static/index.html`, `static/style.css`, `static/app.js`: browser interface without a build step.
- `test_explore.py`: checks destination-specific waits against the existing lookup, terminal/no-service behavior, holiday/late-night service, and station-hour agreement with validated exports.

```sh
python3 -m unittest utilities.schedule_explorer.test_explore
node --check utilities/schedule_explorer/static/app.js
```

Tests use the generated snapshot and skip with an explicit message if it is absent. The HTTP smoke check verifies the moved static assets and metadata endpoint.

This is a schedule-data explorer utility, not the map editor or a published shared library. The separately specified [interactive map/itinerary editor](../../frontend/map_editor/README.md) and optimizer remain their own product work.

## Maintenance plan

The current explorer is the inspection baseline, not a prerequisite for every new editor feature.

| Work | Trigger/dependency | Completion check |
|------|--------------------|------------------|
| Adopt a regenerated snapshot | Backend export refresh | Reload the server; coverage/source labels match the new manifest, and integrity checks use dates served by that snapshot. |
| Maintain export compatibility | Backend B1 changes a consumed schema | Update the reader and its contract checks together; malformed/incompatible exports have a clear error. |
| Extend to Silver Line | Backend B4 supplies validated Silver exports | Route/boarding-stop selection and timetable views preserve direction and scope labels; rail-only behavior remains correct. |

The existing tests include examples tied to the recorded October–December 2026 snapshot. Review those dates and expected values when adopting another feed; do not treat unchanged old expectations as validation of new data.
