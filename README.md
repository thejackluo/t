# T Run

Boston MBTA all-stations planning, organized as separate projects with shared rule references.

Start with the [interactive-map design overview](docs/INTERACTIVE-MAP-PLAN.md) for the ideas connecting the backend, map editor, and route search.

| Part | Responsibility | Start here |
|------|----------------|------------|
| **Backend — rail schedules** | Build/import schedules, daily tables, lookup, validation | [backend/rail_schedule/](backend/rail_schedule/README.md) |
| **Frontend — map editor** | Google Maps itinerary planning; currently requirements only | [frontend/map_editor/](frontend/map_editor/README.md) |
| **Utility — schedule explorer** | Working browser tool for inspecting the schedule exports | [utilities/schedule_explorer/](utilities/schedule_explorer/README.md) |
| **References** | Supplied Guinness rules and interpretation gaps | [docs/references/](docs/references/GUINNESS-RULES.md) |
| **Operations** | Proposed Git commit sequence and verification | [docs/operations/](docs/operations/COMMIT-PLAN.md) |
| **Archive** | Initial proposals and old session metadata | [docs/archive/](docs/archive/initial-assistant-work/README.md) |

## Open the schedule explorer

From the repository root, with the generated exports already in `output/`:

```sh
python3 -m utilities.schedule_explorer.explore
```

Open **http://127.0.0.1:8000**. To build exports first, follow the [backend guide](backend/rail_schedule/README.md).

`data/` and `output/` are shared local artifacts, ignored by Git. The current exports are rail-only; the supplied Guinness rules require Silver Line for a full attempt, with product support planned later.

See [the documentation guide](docs/README.md) for how current planning, references, operations, and historical material fit together.
