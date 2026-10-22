# Start here

> Archived overview of the former layout. File tables and setup references below are historical.

## The short version

We have **schedule data and tools**, plus **a plan for the map application**. The clickable map and fastest-route search are still to be built.

### What you can use now

Open the local file `output/MBTA_Rail_Scheduling.xlsx` for the rail schedules, service dates, station hours, and wait calculator. It uses a dated MBTA schedule snapshot, not live arrival predictions. Its recorded published coverage is October 14–December 12, 2026.

The saved validation report records a passing check of the exported schedules. The separate workbook guide at `docs/RAIL-SCHEDULE-API-PLAN.md` explains the sheets, refresh process, and limits.

### What we build next

1. Establish the station list and connections using the existing schedule work.
2. Build a Google Map with transit overlay and selectable MBTA stations.
3. Let you drag ride/run segments into a connected itinerary, save it, and see missing stations.
4. Calculate realistic trip times, including waits and transfers.
5. Search for faster routes.
6. Add an offline, phone-friendly attempt view.
7. Add **Silver Line** map, schedule, and coverage support.

The detailed [roadmap](planning/ROADMAP.md) is a future work list, not a claim that those features already exist.

## What the files are

| File or folder | Plain-English purpose |
|----------------|-----------------------|
| `README.md` | The short front page. |
| `docs/` | All written explanations, research, and plans. Start with this guide. |
| `docs/planning/PROJECT.md` | What we are trying to build and the decisions so far. |
| `docs/planning/ROADMAP.md` | The order in which we plan to build it. |
| `docs/planning/REQUIREMENTS.md` | Detailed checklists for what each feature should do. |
| `docs/planning/STATE.md` | A bookmark so the coding assistant knows where work stopped. |
| `docs/planning/config.json` | GSD workflow settings. |
| `docs/planning/phases/` | Space for detailed work plans for individual phases. |
| `docs/INTERACTIVE-MAP-PLAN.md` | Detailed brainstorming about the map, itinerary editor, and route search. |
| `docs/MAP-EDITOR-REQUIREMENTS.md` | Current Google Maps editor decisions, proposed defaults, and first-application acceptance steps. |
| `docs/GUINNESS-RULES.md` | Structured extraction of the user-supplied Boston application guidelines and missing source attachments. |
| `docs/RAIL-SCHEDULE-API-PLAN.md` | How the existing workbook and schedule data work. |
| `docs/RESEARCH.md` | Sources and research notes, including record-category questions. |
| `docs/DEVELOPMENT.md` | Technical setup instructions. |
| `build_schedule.py` | Reads official MBTA data and builds the Excel workbook and data tables. |
| `schedule_lookup.py` | Finds the next scheduled departure and wait for a chosen station/date. |
| `validate_schedule.py` | Checks the generated schedules against the source data and selected API results. |
| `output/` | Generated workbook, compressed data tables, source manifest, and validation report. |
| `requirements.txt` | Python libraries needed by the scheduling tools. |
| `scripts/install-gsd.mjs` | Reinstalls the coding assistant's GSD tools. |
| `AGENTS.md` | Instructions for coding assistants working on this project. |
| `.opencode/` | Installed OpenCode/GSD commands, skills, and helper software. You normally do not edit this. |
| `.planning` | A shortcut to `docs/planning/`, because GSD expects that name. It is the same files, not a second copy. |
| `.git/` | Git's repository metadata. |
| `.gitignore` | Tells Git to skip generated files, downloaded data, and local secrets. |
| `.node-version` | Records the JavaScript runtime version used for GSD setup. |
| `__pycache__/`, `.venv/` | Generated Python cache and local dependency environment, when present. |
| `data/` | Downloaded source feeds and generated data, when present. |

## Record rules

The user supplied application-specific Boston guidelines: **Silver Line is required for the full record attempt**. Its implementation remains planned for Phase 7, so rail-only scenarios are rehearsals, not full-record completion. The extracted rules remain outside this archive at `docs/GUINNESS-RULES.md`; the guidelines' attached station-list image and separate evidence guide are still needed.
