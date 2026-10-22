# T Run — Boston Subway Record Planner

> Archived repository front page. Links below have been adjusted for this archive; descriptions reflect the earlier session.

A project for planning an all-stations MBTA speedrun and a potential Guinness World Records attempt.

## What exists today

- **A scheduling workbook:** local file `output/MBTA_Rail_Scheduling.xlsx`, containing published rail schedules, service calendars, and a wait calculator.
- **Python utilities:** build the workbook, look up the next scheduled departure, and check the exported data.
- **The application plan:** an interactive subway map, editable itinerary, and eventually route optimization. The interactive app is not built yet.

**Silver Line support is planned for later**, after the rail version.

## Start here

**[Former plain-English guide → DOCUMENTATION-README.md](DOCUMENTATION-README.md)**

All planning, research, and setup documentation now lives in **`docs/`**.

- [Build order](planning/ROADMAP.md)
- [Map design and ideas (current location)](../../INTERACTIVE-MAP-PLAN.md)
- Workbook instructions remain at `docs/RAIL-SCHEDULE-API-PLAN.md` in the repository.

The local repository is initialized on `main`. The earlier setup used GSD Core, the maintained successor to Get Shit Done; [historical setup details](DEVELOPMENT.md) are retained for reference.
