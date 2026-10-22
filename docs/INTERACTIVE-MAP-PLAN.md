# Interactive MBTA map and record-attempt planner

> Design overview, kept here in `docs/` at the user's request. This document collects the architecture and brainstorming; the owning projects hold the implementation requirements and data plan.

> **Current direction:** Google Maps canvas with transit overlay, mode-first station-to-station dragging, editable street-running routes, and schedule-based totals. Read the [map editor requirements](../frontend/map_editor/REQUIREMENTS.md), [backend schedule plan](../backend/rail_schedule/PLAN.md), and [supplied Guinness rules](references/GUINNESS-RULES.md) for current decisions. Optional schematic ideas below are exploratory; they do not override the selected Google Maps canvas.

## Product direction

**Build a planning cockpit:** a Google Maps view of the subway network, an editable chronological itinerary, and a station-coverage checklist, all reflecting the same transit graph.

The first useful version should let us answer: “Have we covered every required station, in what order, with which transfers, and what remains?” Once that works, add the timetable engine to answer: “Can we actually board those trains, and how long does the whole attempt take?”

## 1. Turning the subway map into an interactive map

### Use official data for identity and connectivity

1. Download and retain one dated MBTA GTFS ZIP.
2. Import `routes`, `stops`, `trips`, `stop_times`, `calendar`, and `calendar_dates`; use `transfers`, `pathways`, `shapes`, and feed metadata where available.
3. Select the challenge's route IDs and the chosen date's service. Preserve other modes only if explicitly enabled as connector transport.
4. Build the inventory of station complexes and child boarding stops, keeping route memberships and explicit grouping overrides.
5. Derive directed ride connections from consecutive stops on actual trip patterns. Do not infer station order from API result ordering or nearby coordinates.
6. Add directed transfer/walking edges with a source and a measured or stated cost. Never connect visually crossing lines automatically.
7. Review a generated inventory and graph report before drawing the map.

### Keep presentation separate from routing

The selected first canvas is Google Maps with application-owned MBTA station handles and route geometry. The transit graph determines connectivity and travel time, independently of the visual base map. A separate schematic could be added later; the following SVG approach is an optional presentation idea rather than the first implementation.

Use the official subway map as a visual reference, then create an editable SVG layout with one layout record per station ID and explicit line/branch paths. Keep label offsets and line geometry outside the routing dataset. The resulting layout can be tuned without changing travel times or connectivity.

For that optional schematic view, SVG makes station dots, line segments, labels, direction arrows, and route overlays interactive and inspectable. A raster/PDF background can help initial tracing, but clicked pixels must resolve to stable station IDs. The rendering should remain functional without the reference image.

Geographic coordinates are retained for a later street/walking view. Schematic distance is never a walking-distance estimate.

## 2. The planning screen

```text
┌───────────────────────────────────────────────────────────────────┐
│ Scenario · service date/start time · ruleset · save/export         │
├────────────────┬───────────────────────────┬──────────────────────┤
│ Search/filter  │ Google Maps + MBTA routes │ Ordered itinerary    │
│ Required set   │                           │ Start / ride / wait  │
│ Missing stops │ Route direction + repeats │ Transfer / walk      │
│ Coverage N/N  │ Selected station details  │ Finish / totals      │
├────────────────┴───────────────────────────┴──────────────────────┤
│ Candidate comparison · time breakdown · fragile connections       │
└───────────────────────────────────────────────────────────────────┘
```

Core interactions:

- Click a station to inspect served routes, platform choices, planned visits, and notes; select “add waypoint” explicitly.
- Choose start/end freely or pin either endpoint. A fixed endpoint should constrain search rather than just change its display.
- Drag itinerary rows to reorder; expand rows to inspect intermediate stops and chosen branches.
- Show visited/planned/missing/excluded states using rings, icons, and text in addition to color.
- Highlight repeated segments and numbered direction arrows; one thick line must not hide several traversals.
- List uncovered stations directly so map-label density does not conceal an incomplete route.
- Let users exclude a station only through an explicit ruleset edit with a reason.
- Save “fastest scheduled,” “larger connection buffers,” and other candidates for side-by-side inspection.

Mobile attempt mode replaces the three-column layout with next action, next platform/direction, time buffer, and the remaining-stations checklist.

## 3. Model that keeps map, schedule, and coverage consistent

| Entity | Important fields |
|--------|------------------|
| Dataset | source URL, retrieval timestamp, SHA-256, feed version/validity, import schema version |
| Station | canonical station/complex ID, constituent stops, names, route memberships, latitude/longitude |
| Boarding stop | original GTFS stop ID, parent station, platform metadata |
| Layout | station ID, schematic x/y, label placement; independent geometry for branch paths |
| Ride pattern | route ID, direction, ordered boarding stops and station coverage sequence |
| Scheduled connection | trip/service IDs, origin/destination stop IDs, departure/arrival service-day seconds |
| Transfer/walk | directed endpoints, duration, allowed mode, fare/exterior flags, provenance/uncertainty |
| Ruleset | version, required inventory, grouping/visit predicate, connector modes, start/end policy, category/rule provenance |
| Scenario | dataset and ruleset IDs, date/start time, endpoint constraints, waypoints, explicit legs, timing assumptions |
| Attempt event | event ID, event type, timestamp, related stop/trip, manual confirmation, correction reference |

A station is a **coverage entity**; a platform is a **routing entity**. That distinction lets Park Street or Downtown Crossing count consistently while preserving actual transfer costs. Group stations by source identity and explicit reviewed rules, never by name alone.

Coverage derives from traversed trip stop sequences plus the selected visit predicate. Walking into a station, transferring through it, or passing without a qualifying stop should not silently earn coverage. Keep arrival/departure/boarding/alighting facts so the rule can be evaluated explicitly.

## 4. Timing engine

For every candidate, report:

**Elapsed time = rides + waits + transfers + walks + explicit turnaround/other costs.**

The evaluator must select feasible departures, not add an average time to each drawn line segment:

- Apply `calendar` and exception dates for the chosen service date.
- Preserve GTFS service-day times beyond 24:00; do not roll them to an unrelated day's service.
- Model timezone/DST using agency-local service-day semantics; avoid naive wall-clock subtraction.
- Retain vehicle/trip continuity so staying onboard does not charge a fictitious new wait.
- A terminal reversal is not automatically an instant same-train trip; require a supported continuation or an explicit boarding assumption.
- Enforce minimum platform transfers and reboard the next feasible trip if a connection is missed.
- Keep scheduled, predicted, and observed values distinct with source times.
- Keep proposed walking edges separate until distance, access, time, and rules permission are reviewed.

For user-authored waypoints, search between consecutive waypoints with timetable-aware routing. The full candidate must then be evaluated end-to-end, because changing one transfer changes all later departures. Surface when expansion chooses a different pattern and allow users to pin ride legs.

## 5. Finding a fast all-stations route

This is a time-dependent graph-coverage problem. Stations and track segments can be revisited. Ordinary start-to-destination shortest paths or a station-order TSP with fixed pair costs do not capture it faithfully.

### Practical search strategy

1. Build and rehearse at least one complete manual baseline.
2. Generate seeds using branch/terminal ordering and plausible start/end choices. Expand these into actual stop sequences, preserving shared trunks and required coverage.
3. Vary endpoint choices, branch order, transfer choices, permitted walking links, and start time.
4. Use beam search and/or multi-start local search to propose sequences. Keep a bounded frontier and show the best feasible candidate as search progresses.
5. Score every candidate with the shared timetable evaluator; reject incomplete or infeasible routes.
6. Use worker execution, cancellation, a fixed random seed, dataset/ruleset hashes, and a time budget.
7. Verify the best candidates independently against explicit leg sequences and the required inventory.

If using a state-space search, state must include sufficient position, time, onboard/trip context, and covered-set information. Dominance pruning is valid only when those states are genuinely compatible; “earlier at the same station” alone is insufficient. Use scalable bitsets rather than JavaScript's 32-bit bitwise mask for network-wide coverage.

Report **best found within the search budget**, elapsed scheduled duration, assumptions, and uncertainty. A static simplified graph can help generate seeds or lower bounds, but does not prove the timetable result optimal.

### Route brainstorming worth testing

- **Endpoint economics:** start at an outlying required endpoint and finish at another to reduce return mileage; compare all plausible endpoint pairs rather than picking one by intuition.
- **Green branch sequencing:** compare repeated shared-trunk rides with allowed inter-branch walking connectors. Cleveland Circle/Reservoir and Boston College/Cleveland Circle are candidates for field measurement, not assumed edges.
- **Red branch handling:** explicitly compare Ashmont, Braintree, and the Mattapan continuation so a branch junction does not hide omitted stations.
- **Blue connection risk:** compare the available in-network transfers and permitted street connections using real departure windows.
- **Extension coverage:** ensure both current northern Green branches are represented by the dated feed and ruleset.
- **Start-time sweep:** a route that is slower in fixed edge weights can win when its connections line up. Test multiple start times on the actual intended service day.
- **Risk-adjusted candidate:** retain a slightly slower scheduled plan if it avoids a connection whose failure would cost a full headway.

These are search hypotheses. None is a recommended final route until evaluated and checked against the chosen rules.

## 6. Guinness and experimental challenge profiles

Use a rail-only rehearsal profile for the initial Red, Orange, Blue, Green B/C/D/E, and Mattapan implementation. The supplied [Guinness rules](references/GUINNESS-RULES.md) require Silver Line for the full attempt: rail-only coverage must never be labelled full record completion.

Keep mode/route selection configurable from the start; Silver Line includes bus-mode routes and stops that may lack rail-style parent stations. Add a separate rail-plus-Silver profile rather than changing the meaning of saved rail-only attempts. Its delivery remains later work; old Phase 7 numbering is historical.

The supplied guidelines already describe stopped-service train visits, allowed foot/scheduled-public-transport connectors, continuous first-door-close to final-platform timing, closure exceptions, and evidence requirements. Link to the reference rather than re-deciding those rules here.

Remaining inputs include the attached required-station image, the separate evidence guide, the intended service date/start time, and clarification of the Silver-specific visit/boundary wording where needed. There is no verified current target time in this project yet.

## 7. Proposed implementation architecture

- **Client:** TypeScript + React with Vite for a small map-first application.
- **Rendering:** selected Google Maps canvas with application-owned MBTA station handles and ride/foot geometry; an SVG schematic remains an optional later view.
- **Importer:** reuse the Python tools in `backend/rail_schedule/`, exposing normalized versioned artifacts to the frontend rather than starting a second importer. Keep raw feeds out of Git.
- **Domain core:** framework-independent graph, coverage validator, scenario serializer, and timetable evaluator shared by editing and optimization.
- **Persistence:** IndexedDB for saved scenarios and attempt events; portable JSON/CSV exports.
- **Search:** Web Worker boundary so optimization remains cancellable and the map remains responsive. Measure timetable size before choosing a compact browser bundle versus server-side evaluation.
- **Live context:** later small server-side MBTA proxy with caching and a private API key; static/offline planning still works when it is unavailable.
- **Offline:** cache the chosen dataset subset, application assets, and itinerary; make cached-data version and freshness visible.

Possible internal modules within the map editor frontend (not created yet):

```text
src/domain/          network, rules, coverage, scenario, timetable
src/map/             Google Maps canvas, station handles, route overlays
src/planner/         editor, timeline, comparison
src/optimizer/       candidate search and worker
src/attempt/         mobile instructions and event log
public/network/      reviewed versioned display/network assets
```

The stack is proposed, not installed. No account system or production hosting choice is required for the first milestone.

## 8. Validation that matters

- Feed audit: every required station has source IDs, map coordinates, and incident routing edges; missing parents or dangling edges are reported.
- Branch fixtures: both Red branches, each Green branch, shared trunks, Mattapan transfer, and reviewed extension stations.
- Timetable fixtures: missed transfer, opposite platform, same-vehicle continuation, terminal reversal, unavailable service, exception day, and post-midnight trips.
- Coverage fixtures: duplicates do not inflate totals; invalid walking/pass-through visits are rejected under the chosen predicate.
- Small exact cases: compare heuristic results against exhaustive search on tiny networks to catch invalid pruning and scoring.
- Persistence exercise: save/reload a complete route and an active attempt with corrections; disconnect the network and reopen.
- Field rehearsal: time key transfers and compare scheduled versus observed legs; use the findings to recalibrate costs and delay assumptions.

## 9. First implementation session

1. Confirm a provisional rules profile and representative service date.
2. Scaffold the client and domain modules, with package versions chosen from current documentation at implementation time.
3. Review `backend/rail_schedule/build_schedule.py`, then reuse or extend ingestion to produce the network artifacts and source manifest.
4. Review the station inventory and connectivity report before establishing a count.
5. Render application-owned station handles and routes on the selected Google Maps canvas.

The current delivery steps and acceptance criteria are in the [map editor requirements](../frontend/map_editor/REQUIREMENTS.md). The [original seven-phase roadmap](archive/initial-assistant-work/planning/ROADMAP.md) remains historical reference material.
