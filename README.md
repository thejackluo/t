# T Run

Plan an all-stations Boston MBTA journey, experiment with rail and running connections, and work toward a Guinness World Record attempt.

## What exists today

| Part | Status | Purpose |
|------|--------|---------|
| [Rail schedule backend](backend/rail_schedule/README.md) | Working Python tools | Import official schedules, generate the workbook/daily tables, look up scheduled waits, and validate exports. |
| [Schedule explorer](utilities/schedule_explorer/README.md) | Working local browser utility | Inspect stations, departures, holidays, and scheduled waits using those exports. |
| [Map editor](frontend/map_editor/README.md) | Early prototype work in progress | Build a Google Maps workspace for connected Ride/Run itineraries, timing, and coverage; delivery criteria remain to be verified. |

Routing/evaluation work has begun in `backend/rail_schedule/itinerary.py`, with a local editor server in `frontend/map_editor/server.py`. Their presence is not yet evidence that the end-to-end editor/evaluator milestone is complete. Automatic route optimization and the attempt-day companion remain later work. The explorer is a separate data-inspection tool, not the map editor.

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

**Next concrete task:** agree the B1/F1 data contract using the existing exports, then produce a small end-to-end example. The Google map shell can be developed in parallel once its station input is understood.

- [Backend delivery plan](backend/rail_schedule/PLAN.md#delivery-plan): data contract → graph → timetable evaluator.
- [Frontend delivery plan](frontend/map_editor/PLAN.md): input contract → map → editing → timing → persistence/comparison.
- [Explorer maintenance plan](utilities/schedule_explorer/README.md#maintenance-plan): keep the existing inspection utility compatible with backend exports.

These work packages define the delivery and verification checklist for ongoing implementation; they are not completed tasks or the old archived phase numbering.

## Later work and record scope

- **Silver Line:** required by the supplied rules for the full attempt; implementation comes after the rail foundation. Rail-only results must be labelled **rehearsals**.
- **Optimization:** search for better routes after the same evaluator can validate a manual baseline.
- **Attempt day:** offline instructions, observations/evidence logging, and optional live predictions.

The [Guinness reference](docs/references/GUINNESS-RULES.md) records the supplied rules. Its attached station-list image and separate evidence guide are still needed. Their absence limits official inventory/evidence validation, but does not prevent experimenting with the existing rail dataset.

## Where to read next

- [Documentation guide](docs/README.md): which document answers which question.
- [Design overview](docs/INTERACTIVE-MAP-PLAN.md): architecture and brainstorming.
- [Map editor requirements](frontend/map_editor/REQUIREMENTS.md): confirmed behavior and proposed defaults.
- [Git operations record](docs/operations/COMMIT-PLAN.md): completed repository-organization commits and guidance for future changes.
