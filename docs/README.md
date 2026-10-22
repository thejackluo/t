# Documentation and planning

Planning belongs to the project that owns the work. Shared rules, repository operations, and historical material have different homes. Start with the [root README](../README.md) for current status and the cross-project build order.

## Which document answers my question?

| Question | Read |
|----------|------|
| What works now, and what comes next? | [Root README](../README.md) |
| How do I run a component? | That component's README |
| What should the map editor do? | [Frontend REQUIREMENTS](../frontend/map_editor/REQUIREMENTS.md) |
| What are the next tasks, their dependencies, and completion checks? | [Frontend PLAN](../frontend/map_editor/PLAN.md), [backend PLAN](../backend/rail_schedule/PLAN.md#delivery-plan) |
| Why is the design shaped this way? | [Design overview](INTERACTIVE-MAP-PLAN.md) |
| What rules apply to the attempt? | [Guinness reference](references/GUINNESS-RULES.md) |
| What was committed, and how should future work be split? | [Git operations](operations/COMMIT-PLAN.md) |

## Document ownership

| Category | Canonical location | What belongs there |
|----------|--------------------|--------------------|
| Design overview | [INTERACTIVE-MAP-PLAN.md](INTERACTIVE-MAP-PLAN.md) | Cross-project architecture and brainstorming, kept visible in `docs/`; project requirements remain authoritative. |
| Backend schedule project | [backend/rail_schedule/README.md](../backend/rail_schedule/README.md), [PLAN.md](../backend/rail_schedule/PLAN.md) | Schedule ingestion, daily tables, lookup/validation, data semantics, and backend integration. |
| Map editor frontend project | [README.md](../frontend/map_editor/README.md), [REQUIREMENTS.md](../frontend/map_editor/REQUIREMENTS.md), [PLAN.md](../frontend/map_editor/PLAN.md) | Setup/status, expected behavior, and separately broken-down delivery work. |
| Explorer utility | [utilities/schedule_explorer/README.md](../utilities/schedule_explorer/README.md) | Running the inspection tool, available views, data limitations, and tests. |
| Reference material | [references/GUINNESS-RULES.md](references/GUINNESS-RULES.md) | Supplied rules, source status, interpretation gaps, missing attachments. This is a reference, not a software project plan. |
| Operations | [operations/COMMIT-PLAN.md](operations/COMMIT-PLAN.md) | Completed organization commits, review/staging guidance, and verification commands. |
| Historical archive | [archive/initial-assistant-work/README.md](archive/initial-assistant-work/README.md) | Superseded research, initial plans, retired installer, and old session snapshots. |

## How to keep this organized

- Use **README = status/how to run**, **REQUIREMENTS = what it must do**, and **PLAN = how to deliver it**. The backend plan also owns its detailed data-source notes.
- Update each project's plan rather than creating another top-level execution roadmap. B1–B4 and F1–F5 identify current proposed work packages; archived phase numbers are historical.
- Mark a deliverable complete only when its listed checks actually pass. Distinguish confirmed user decisions from proposed implementation details.
- Reference the Guinness page from project plans instead of copying the rules into each plan.
- Put repository maintenance instructions under `operations/`.
- Keep old proposals in `archive/`; they do not override current requirements.
- Store generated source feeds, outputs, credentials, and private attempt evidence outside tracked source.

The previous generic `docs/planning/` folder and `.planning` alias are retired. Their remaining session files have been preserved under the archive's `session/` folder; they are not a current execution queue. Generated `.opencode/` tools remain local and ignored.
