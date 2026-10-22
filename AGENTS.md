# Project guidance

- Read `README.md` and the owning project's guide before implementing. Backend schedule planning is in `backend/rail_schedule/PLAN.md`; frontend map-editor decisions are in `frontend/map_editor/REQUIREMENTS.md`; the schedule explorer is under `utilities/schedule_explorer/`.
- Shared rules live in `docs/references/GUINNESS-RULES.md`. Repository operations and proposed commits live in `docs/operations/COMMIT-PLAN.md`.
- Initial assistant plans and old session metadata are archived under `docs/archive/initial-assistant-work/`; treat them as reference, not an active execution plan. Do not recreate generic `.planning` state without an explicit workflow request.
- Give concise status updates listing work in progress.
- Preserve MBTA identifiers, directed transfers, source timestamps, calendars, and boarding restrictions. Keep scheduled, predicted, estimated, and observed times distinct.
- Current map-editor decisions select Google Maps. Supplied rules require Silver Line for the full attempt; implementation remains later work and rail-only completion is a rehearsal.
- Shared local data and generated exports stay in repository-level `data/` and `output/`; resolve defaults from file locations rather than the caller's working directory.
- Require explicit user instructions before committing, pushing, creating remote repositories, or submitting external applications.
- Keep credentials, downloaded feeds, generated outputs, and private attempt evidence out of Git.
