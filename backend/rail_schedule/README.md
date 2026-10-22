# Rail schedule backend

**Responsibility:** import official MBTA rail schedules, generate auditable tables/workbooks, and answer schedule lookups. This is the backend/data project, not the browser map editor. It currently provides Python modules and command-line tools; a multi-leg evaluator or production HTTP API is future work.

## What lives here

| File | Purpose |
|------|---------|
| `build_schedule.py` | Reads a GTFS snapshot and builds the workbook, service calendar, daily station hours, departures, and other exports. |
| `schedule_lookup.py` | Finds the next boardable scheduled departure and passenger-specific scheduled wait. |
| `validate_schedule.py` | Checks exports against the source feed and optionally samples the MBTA API. |
| `paths.py` | Resolves shared source-data/output locations from the repository, regardless of working directory. |
| `requirements.txt` | Python dependencies for building and validating workbooks. |
| [PLAN.md](PLAN.md) | Data sources, calendar/holiday/overnight semantics, workbook details, and future backend integration. |

There is no separate daily-schedule script today: `build_schedule.py` generates the daily `station_hours.csv.gz` and `service_calendar.csv.gz` tables. They stay part of this project.

## Run from the repository root

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/rail_schedule/requirements.txt
.venv/bin/python -m backend.rail_schedule.build_schedule
```

The build downloads the current MBTA feed unless `--gtfs /path/to/feed.zip` is supplied. It also retrieves a dated alert snapshot. Downloaded feeds remain under repository-level `data/`; generated results remain under `output/`. They are ignored by Git.

Example lookup using existing exports (no third-party dependencies):

```sh
python3 -m backend.rail_schedule.schedule_lookup --date 2026-10-22 --time 08:00:00 --route Red --station place-pktrm --direction 0 --destination Ashmont
```

Validate an existing feed/output pair offline:

```sh
.venv/bin/python -m backend.rail_schedule.validate_schedule --gtfs data/MBTA_GTFS.zip --skip-api
```

Omit `--skip-api` for dated API spot checks. Validation writes its report to the selected output folder. Use the archived ZIP named in `output/manifest.json` to reproduce the exact source snapshot. `--out` and lookup's `--data` accept alternative export directories.

Direct script paths also work, e.g. `python3 backend/rail_schedule/schedule_lookup.py --help`. Default source/output paths are repository-relative; explicitly supplied relative arguments remain relative to the caller's working directory.

## Project boundary

The [schedule explorer](../../utilities/schedule_explorer/README.md) consumes these exports for inspection. The [map editor](../../frontend/map_editor/README.md) will consume schedule/network data for itinerary planning. Browser display code does not belong here.

The current dataset is rail-only. Silver Line support is later work, and the [supplied Guinness rules](../../docs/references/GUINNESS-RULES.md) require it for the full attempt.
