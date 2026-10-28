# T Run

Plan an all-stations Boston MBTA journey, experiment with rail and running connections, and work toward a Guinness World Record attempt.

## What exists today

| Part | Status | Purpose |
|------|--------|---------|
| [Rail schedule backend](backend/rail_schedule/README.md) | Working Python tools | Import official schedules, generate the workbook/daily tables, look up scheduled waits, and validate exports. |
| [Schedule explorer](utilities/schedule_explorer/README.md) | Working local browser utility | Inspect stations, departures, holidays, and scheduled waits using those exports. |
| [Map editor](frontend/map_editor/README.md) | Working local prototype; live Google canvas verified | Create track-following rail/run/walk itineraries, evaluate schedules/coverage, save candidates, and export to Google My Maps. |

Routing/evaluation is in `backend/rail_schedule/itinerary.py`, with the route studio in `frontend/map_editor/server.py`. Its own-data preview, timetable/KML workflows, and live Google canvas (with a user-supplied restricted browser key) are verified; pedestrian street suggestions and private My Maps import still need live verification. The full editor milestone still has remaining criteria, including candidate comparison and refined timing/access controls. Automatic optimization and the attempt-day companion remain later work.

## Repository layout

```text
backend/rail_schedule/         Schedule scripts, dependencies, README, backend PLAN
frontend/map_editor/           Frontend README, REQUIREMENTS, delivery PLAN
utilities/schedule_explorer/   Explorer server, browser assets, tests, README
docs/INTERACTIVE-MAP-PLAN.md    Cross-project design ideas and architecture
docs/references/               Supplied Guinness rules
docs/operations/               Git/repository maintenance
docs/archive/                  Superseded plans, retired setup, session snapshots
data/                         Local downloaded feeds (ignored by Git)
output/                       Shared generated exports/workbook (ignored by Git)
```

## Try the working tools

### Map route studio

```sh
python3 -m frontend.map_editor.server
```

Open **http://127.0.0.1:8001** to create track-following rail/run/walk itineraries and export KML for Google My Maps. Requires Python 3.11+, generated schedule exports, and their pinned GTFS archive. The geographic preview works without a browser key; a configured key enables the Google Maps canvas. [Editor setup and usage](frontend/map_editor/USAGE.md).

### Schedule explorer

From the repository root, with the generated exports already in `output/`:

```sh
python3 -m utilities.schedule_explorer.explore
```

Open **http://127.0.0.1:8000**. To build exports first, follow the [backend guide](backend/rail_schedule/README.md).

The explorer needs Python 3.9+ and no third-party packages. Workbook building/validation needs the backend's Python dependencies. The recorded local snapshot covers **October 14–December 12, 2026**; other checkouts may have different data or no generated exports. Treat `output/manifest.json` as the source of truth for the loaded snapshot.

## What we build next

The first application milestone is **one editable, saved rail-rehearsal itinerary with realistic timing and visible station coverage**.

| Order | Deliverable | Owner and detailed plan |
|-------|-------------|-------------------------|
| 1 | Define the data exchanged between schedules and the editor, with dataset/ruleset identity. | Backend **B1** and frontend **F1** in their plans below. |
| 2 | Add directed ride/transfer connectivity; render the Google map and selectable stations. | Backend **B2**; frontend **F2** can start alongside it. |
| 3 | Create a connected itinerary using explicit Ride/Run/Walk/Transfer legs and undo. | Frontend **F3**, using the B2 graph. |
| 4 | Evaluate feasible departures and recalculate downstream timing after an edit. | Backend **B3**, integrated in frontend **F4**. |
| 5 | Save/reload candidates and compare time, coverage, transfers, and running distance. | Frontend **F5**. |

**Next concrete task:** verify pedestrian street suggestions (Routes API) and import an exported KML into the private My Maps project, then close the remaining milestone acceptance gaps. Review the [implemented API/scenario contract and example](frontend/map_editor/USAGE.md) against B1/F1. The [implementation commit plan](docs/operations/MAP-EDITOR-COMMIT-PLAN.md) defines the source-control sequence.

- [Backend delivery plan](backend/rail_schedule/PLAN.md#delivery-plan): data contract → graph → timetable evaluator.
- [Frontend delivery plan](frontend/map_editor/PLAN.md): input contract → map → editing → timing → persistence/comparison.
- [Explorer maintenance plan](utilities/schedule_explorer/README.md#maintenance-plan): keep the existing inspection utility compatible with backend exports.

These work packages define the delivery and verification checklist for ongoing implementation; they are not completed tasks or the old archived phase numbering.

## Later work and record scope

- **Silver Line:** required by the supplied rules for the full attempt. SL1–SL5/SLW are built into the schedule and ride like any line, with Silver coverage tracked separately from the 125 rail stations because the Silver visit rule still awaits clarification. Rail-only results must be labelled **rehearsals**.
- **Buses:** the supplied rules allow scheduled public transport between lines, so direct MBTA bus connectors between two stations are offered (Bus mode, and in Auto) with the walk to/from the stop estimated; a bus never earns station coverage.
- **Backtracking check:** the studio measures how much of a plan re-rides track already covered (speedrun style), lists each repeated stretch, and suggests bus, Silver, rail or run shortcuts with the time each saves — including jumping to the far end of the next new stretch and riding it in reverse.
- **Optimization:** search for better routes after the same evaluator can validate a manual baseline.
- **Attempt day:** offline instructions, observations/evidence logging, and optional live predictions.

The [Guinness reference](docs/references/GUINNESS-RULES.md) records the supplied rules. Its attached station-list image and separate evidence guide are still needed. Their absence limits official inventory/evidence validation, but does not prevent experimenting with the existing rail dataset.

## Where to read next

- [Documentation guide](docs/README.md): which document answers which question.
- [Design overview](docs/INTERACTIVE-MAP-PLAN.md): architecture and brainstorming.
- [Map editor requirements](frontend/map_editor/REQUIREMENTS.md): confirmed behavior and proposed defaults.
- [Git operations record](docs/operations/COMMIT-PLAN.md): completed repository-organization commits and guidance for future changes.
