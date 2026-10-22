# Documentation and planning

Planning belongs to the project that owns the work. Shared rules, repository operations, and historical material have different homes.

| Category | Canonical location | What belongs there |
|----------|--------------------|--------------------|
| Design overview | [INTERACTIVE-MAP-PLAN.md](INTERACTIVE-MAP-PLAN.md) | Cross-project architecture and brainstorming, kept visible in `docs/`; project requirements remain authoritative. |
| Backend schedule project | [backend/rail_schedule/README.md](../backend/rail_schedule/README.md), [PLAN.md](../backend/rail_schedule/PLAN.md) | Schedule ingestion, daily tables, lookup/validation, data semantics, and backend integration. |
| Map editor frontend project | [frontend/map_editor/README.md](../frontend/map_editor/README.md), [REQUIREMENTS.md](../frontend/map_editor/REQUIREMENTS.md) | Confirmed interactions, proposed defaults, frontend responsibilities, and delivery/acceptance steps. |
| Explorer utility | [utilities/schedule_explorer/README.md](../utilities/schedule_explorer/README.md) | Running the inspection tool, available views, data limitations, and tests. |
| Reference material | [references/GUINNESS-RULES.md](references/GUINNESS-RULES.md) | Supplied rules, source status, interpretation gaps, missing attachments. This is a reference, not a software project plan. |
| Operations | [operations/COMMIT-PLAN.md](operations/COMMIT-PLAN.md) | Git review/staging/commit sequence and verification commands. |
| Historical archive | [archive/initial-assistant-work/README.md](archive/initial-assistant-work/README.md) | Superseded research, initial plans, retired installer, and old session snapshots. |

## How to keep this organized

- Update each project's existing plan rather than creating another top-level roadmap.
- Reference the Guinness page from project plans instead of copying the rules into each plan.
- Put repository maintenance instructions under `operations/`.
- Keep old proposals in `archive/`; they do not override current requirements.
- Store generated source feeds, outputs, credentials, and private attempt evidence outside tracked source.

The previous generic `docs/planning/` folder and `.planning` alias are retired. Their remaining session files have been preserved under the archive's `session/` folder; they are not a current execution queue. Generated `.opencode/` tools remain local and ignored.
