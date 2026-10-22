# T Run — Boston Subway Record Planner

> Archived initial project brief. Proposed scope and decisions are historical, not an active mandate.

## What This Is

A map-first workspace for planning the fastest trip through Boston's subway system. The team can design and compare all-station itineraries, understand waits and transfers, rehearse alternatives, and follow the selected plan during a record attempt.

The immediate deliverable is a researched project foundation and implementation plan. The application described here is proposed, not yet built.

## Core Value

Make a complete all-stations itinerary understandable, editable, and realistically timed before the team attempts it.

## Requirements

### Validated

None yet — application features have not shipped.

### Active

- [ ] Render a Boston-centered Google Map with transit overlay and interactive MBTA station handles backed by official identifiers.
- [ ] Build, save, and compare complete itineraries with explicit station coverage.
- [ ] Compute feasible travel, waiting, transfer, walking, and turnaround times for a selected service date.
- [ ] Search for faster feasible all-station candidates and explain the tradeoffs.
- [ ] Support a mobile, offline-capable attempt view with editable observations and exportable logs.

Detailed acceptance requirements: [REQUIREMENTS.md](REQUIREMENTS.md).

## Context

- The workspace started empty at `/home/jack/projects/t`; Git now uses `main`.
- Python tools now build a rail scheduling workbook, look up scheduled departures, and validate the exports. The saved validation report records a passing audit; see `docs/RAIL-SCHEDULE-API-PLAN.md`.
- Get Shit Done's original repository is archived and redirects to GSD Core. GSD Core 1.18.0 is installed for OpenCode locally.
- MBTA provides official GTFS schedules and V3 API resources for stops, routes, route patterns, schedules, predictions, and alerts.
- The live rail route query returned Red, Mattapan, Orange, Green-B/C/D/E, and Blue. Route memberships and destinations remain dated data, not permanent code assumptions.
- The user supplied application-specific Guinness guidelines in discussion; see `docs/GUINNESS-RULES.md`. They define stopped-train visits, continuous door-close-to-final-platform timing, foot/scheduled-public-transport transfers, closure exceptions, and evidence requirements. The attached required-station image and separate evidence guide remain missing.
- Silver Line is expressly included in the supplied record definition. Product delivery remains rail first and Silver in Phase 7; a complete rail rehearsal must not be presented as full Guinness coverage. Exact Silver stops and visit/start-finish interpretation require the referenced inventory and any application clarification.
- Confirmed editor behavior: choose Ride/Run before dragging between fixed station locations; preview rail alternatives with explicit transfers; editable pedestrian routes; one connected itinerary with undo; running/walking/internal transfers; free endpoints with optional pins. See `docs/MAP-EDITOR-REQUIREMENTS.md`.
- The team has not selected an attempt date, running/walking pace, or validated station access costs. Timing, local saving, and comparison defaults are proposed in the editor requirements, not yet user-confirmed.

## Constraints

- **Correctness:** a train passing a map dot does not automatically satisfy an unconfirmed visit rule.
- **Timing:** planning must use service calendars and departure times, including overnight service-day conventions.
- **Data:** one versioned station/rule inventory per scenario; updates should expose additions and removals.
- **Usability:** desktop planning first; large touch targets and cached itinerary for attempt day.
- **Scope:** build manual map editing before optimization; use the same graph and evaluator throughout.
- **Operations:** the selected Google Maps canvas requires local service configuration; choose routing services and check current billing/quotas during implementation. Local scenario saving is proposed; no application account system has been selected.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use maintained GSD Core locally | Original Get Shit Done points to this successor | Installed |
| Use transit data as routing authority | A PDF does not encode schedules, platforms, or transfer restrictions | Proposed |
| Google Maps with transit overlay first | User requested street-running experimentation and station-to-station drag editing | Confirmed; supersedes earlier SVG-first proposal |
| Separate station coverage from platform routing | Avoid double-counting while retaining feasible transfer paths | Proposed |
| Rail first, Silver Line later | User requested eventual Silver Line support; preserve configurable modes and coverage inventories | Phase 7 planned |
| Use supplied application guidelines as the planning rule source | User provided specific Boston guidelines, including required Silver Line | Rules extracted; attached station list and evidence guide still needed |

---
*Last updated: 2026-10-21 after repository setup and initial research.*
