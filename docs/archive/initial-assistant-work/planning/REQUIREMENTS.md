# Requirements: T Run

> Archived feature checklist. These are proposed acceptance criteria, not completed features or a current execution plan.

**Defined:** 2026-10-21

**Core value:** Make a complete all-stations itinerary understandable, editable, and realistically timed.

## v1 Requirements

### Dataset and rules

- [ ] **DATA-01**: Import a dated MBTA GTFS snapshot with source URL, retrieval time, feed identity, and checksum.
- [ ] **DATA-02**: Preserve parent stations, platforms, directed trip stop sequences, route patterns, and shared station memberships without merging unrelated same-name stops.
- [ ] **DATA-03**: Produce a reviewable required-station inventory with additions/removals and a count generated from the selected ruleset.
- [ ] **RULE-01**: Save a versioned ruleset sourced to the user-supplied application guidelines, covering required rail-plus-Silver inventory, normal stopped-service visits, station grouping, foot/scheduled-public-transport permissions, closure exceptions with provenance, and continuous first-door-close to final-platform timing. Keep experimental rail-only rehearsal profiles distinct from record-complete coverage; missing station-list attachments and unresolved Silver/boundary interpretations remain explicit. See `docs/GUINNESS-RULES.md`.

### Map

- [ ] **MAP-01**: Pan, zoom, search, and keyboard-select official MBTA station handles on a responsive Boston-centered Google Map with native transit overlay and readable line/branch labels. Own markers and route geometry provide editing identities; native transit context is not promised to support per-line filtering.
- [ ] **MAP-02**: Show station details and distinguish required, planned, visited, and excluded coverage states using symbols as well as color.
- [ ] **MAP-03**: Overlay an itinerary's ordered legs, repeated track traversals, transfers, and direction, keeping display coordinates independent of routing.

### Itinerary editor

- [ ] **PLAN-01**: Choose Ride/Run before dragging between fixed stations to add connected itinerary legs; support insertion/replacement, reordering, removal, optional endpoint pins, undo, and visible disconnected-edit errors. Provide endpoint selection without dragging.
- [ ] **PLAN-02**: Preview selectable rail paths with explicit transfers, and suggest editable pedestrian street routes for outdoor running/walking links. Expand the itinerary into ride/run/walk/transfer/wait/break legs, preserving intermediate stop calls and showing covered, repeated, and missing stations according to the ruleset.
- [ ] **PLAN-03**: Save and reload a versioned scenario JSON containing dataset/ruleset IDs, constraints, itinerary, and assumptions; export the leg table as CSV.
- [ ] **PLAN-04**: Compare at least two saved candidates by elapsed time, coverage, walking, transfers, and fragile connections.

### Timing and search

- [ ] **TIME-01**: Evaluate itineraries against service dates, calendar exceptions, directed trips, departure times, GTFS times beyond 24:00, and America/New_York timezone behavior.
- [ ] **TIME-02**: Include directed platform transfer minimums, entrance/exit costs, explicit terminal turnaround/boarding assumptions, configurable running/walking pace, and missed-connection consequences; recalculate downstream departures after edits and show unavailable journeys as infeasible. Count all in-attempt waits/breaks, exclude pre-start preparation, and label timetable proxies and estimated allowances for first door closure and final platform footfall without implying observed centisecond precision.
- [ ] **OPT-01**: Generate reproducible candidate routes using a fixed seed and time budget, score each with the timetable evaluator, and display feasible incumbent results while searching.
- [ ] **OPT-02**: Compare scheduled duration with a stated delay model and connection buffers; label candidate quality and uncertainty without claiming global optimality.

### Attempt day

- [ ] **RUN-01**: Cache a selected scenario for offline opening and provide a mobile next-leg view, coverage checklist, elapsed time, and manual visit confirmation.
- [ ] **RUN-02**: Append timestamped observations and corrections without erasing original events, persist through reload, and export logs with dataset/ruleset references.
- [ ] **LIVE-01**: Show optional alerts and predictions with observation time and stale/offline indicators, while preserving the planned baseline and user-confirmed progress.

## Later delivery: Silver Line

- [ ] **SILVER-01**: Import a reviewed Silver Line route/stop inventory from official data, including bus-mode routes and stops without parent-station records; do not rely on the rail-only mode filter.
- [ ] **SILVER-02**: Support Silver Line display, itinerary editing, scheduled timing, and coverage alongside rail while preserving direction and distinct boarding stops.
- [ ] **SILVER-03**: Save separate rail-only and rail-plus-Silver challenge profiles; show their required inventories and totals explicitly, and preserve existing rail-only scenarios.

## Later ideas

- Field-measured station-specific walking/access times to replace initial stated assumptions; the editable geographic foot-route overlay is part of the first editor.
- Shared editing and a spectator dashboard.
- Broader bus or commuter-rail challenge profiles.
- Exact optimization on a simplified model, with a documented bound or proof where practical.
- Evidence-file manifests and read-only replay of rehearsals.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| RULE-01 | Phase 1 | Pending |
| MAP-01 | Phase 2 | Pending |
| MAP-02 | Phase 2 | Pending |
| MAP-03 | Phase 3 | Pending |
| PLAN-01 | Phase 3 | Pending |
| PLAN-02 | Phase 3 | Pending |
| PLAN-03 | Phase 3 | Pending |
| PLAN-04 | Phase 4 | Pending |
| TIME-01 | Phase 4 | Pending |
| TIME-02 | Phase 4 | Pending |
| OPT-01 | Phase 5 | Pending |
| OPT-02 | Phase 5 | Pending |
| RUN-01 | Phase 6 | Pending |
| RUN-02 | Phase 6 | Pending |
| LIVE-01 | Phase 6 | Pending |
| SILVER-01 | Phase 7 | Pending |
| SILVER-02 | Phase 7 | Pending |
| SILVER-03 | Phase 7 | Pending |
