# Roadmap: T Run

> Archived delivery proposal. Silver Line remains a recorded user request; phase numbering here is historical.

## Overview

Build a trustworthy network model, make it easy to explore and edit, add scheduled timing, search for better routes, and prepare an attempt-day companion. Validate one complete manually authored itinerary before automated search.

## Phases

- [ ] **Phase 1: Dataset and challenge rules** - Establish the station inventory and graph.
- [ ] **Phase 2: Interactive subway schematic** - Explore and inspect every required station.
- [ ] **Phase 3: Manual itinerary editor** - Author and persist a complete route.
- [ ] **Phase 4: Timetable evaluator and comparison** - Establish realistic, reproducible timing.
- [ ] **Phase 5: Candidate route optimization** - Search and compare faster feasible attempts.
- [ ] **Phase 6: Attempt-day companion** - Follow the route offline with optional live context.
- [ ] **Phase 7: Silver Line support** - Extend the map, schedules, and challenge profiles to Silver Line.

## Phase Details

### Phase 1: Dataset and challenge rules
**Goal**: Establish a reviewable, dated source of truth for stations and service.
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, RULE-01
**Success Criteria**:
1. A reproducible importer generates station, platform, ride, and transfer records from a pinned feed.
2. The team can inspect the exact required inventory and understand how the count was derived.
3. Red branches, Green branches and extension, Mattapan, and shared transfer stations retain correct identities and stop order.
4. An experimental ruleset records unresolved visit and mode questions without implying Guinness approval.
**Plans**: TBD

### Phase 2: Interactive subway schematic
**Goal**: Give the team a recognizable, usable planning canvas.
**Depends on**: Phase 1
**Requirements**: MAP-01, MAP-02
**Success Criteria**:
1. Every required station is searchable and selectable with pointer and keyboard.
2. Pan/zoom, branch labels, station details, and line filters work on desktop and mobile.
3. A data-to-layout audit exposes missing station positions and orphaned map elements.
**Plans**: TBD

### Phase 3: Manual itinerary editor
**Goal**: Author a complete all-station plan without needing the optimizer.
**Depends on**: Phase 2
**Requirements**: MAP-03, PLAN-01, PLAN-02, PLAN-03
**Success Criteria**:
1. Waypoint edits update the ordered itinerary overlay and coverage checklist.
2. All intermediate stops on selected ride legs contribute according to the ruleset; transfer-only presence does not silently count as a ride visit.
3. Save/reload preserves route order, data references, constraints, and assumptions; undo restores the prior edit.
4. A manually authored complete candidate is saved as a reusable rehearsal scenario.
**Plans**: TBD

### Phase 4: Timetable evaluator and comparison
**Goal**: Evaluate candidates using actual scheduled services and transfer costs.
**Depends on**: Phase 3
**Requirements**: TIME-01, TIME-02, PLAN-04
**Success Criteria**:
1. Each ride leg names its service/trip and scheduled boarding and arrival times for the selected date.
2. An intentionally missed connection results in the next feasible departure or an infeasible result.
3. Calendar exceptions, late-night service, and platform changes pass meaningful routing fixtures.
4. Two saved routes can be compared with visible wait, ride, walk, transfer, and elapsed totals.
**Plans**: TBD

### Phase 5: Candidate route optimization
**Goal**: Improve a trusted manual baseline and explain the improvements.
**Depends on**: Phase 4
**Requirements**: OPT-01, OPT-02
**Success Criteria**:
1. Re-running a fixed dataset, ruleset, seed, constraints, and budget reproduces candidate scoring.
2. Every proposed result passes the same coverage and feasibility evaluator as manual routes.
3. Search displays an incumbent result, can be cancelled, and does not block map interaction.
4. Comparisons expose fragile connections and report simulated uncertainty with its assumptions.
**Plans**: TBD

### Phase 6: Attempt-day companion
**Goal**: Turn a rehearsed plan into a dependable on-trip reference.
**Depends on**: Phase 5
**Requirements**: RUN-01, RUN-02, LIVE-01
**Success Criteria**:
1. A cached route opens offline with next-leg instructions and saved confirmed coverage.
2. Reloading preserves an active attempt and its ordered observation/correction history.
3. Prediction outages and stale alerts are visible without overwriting the scheduled plan.
4. A rehearsal exports a usable timeline and identifies timing assumptions to recalibrate.
**Plans**: TBD

### Phase 7: Silver Line support
**Goal**: Add Silver Line planning alongside rail, with explicit route/stop scope for each challenge.
**Depends on**: Phase 6
**Requirements**: SILVER-01, SILVER-02, SILVER-03
**Success Criteria**:
1. A reviewed Silver Line inventory is imported using explicit route selection, including bus routes and boarding stops without parent stations.
2. Silver Line legs appear on the map and in the editor with direction-aware scheduled timing and coverage.
3. Rail-only and rail-plus-Silver profiles show separate required inventories, and existing rail-only scenarios still load correctly.
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Dataset and challenge rules | 0/TBD | Not started | - |
| 2. Interactive subway schematic | 0/TBD | Not started | - |
| 3. Manual itinerary editor | 0/TBD | Not started | - |
| 4. Timetable evaluator and comparison | 0/TBD | Not started | - |
| 5. Candidate route optimization | 0/TBD | Not started | - |
| 6. Attempt-day companion | 0/TBD | Not started | - |
| 7. Silver Line support | 0/TBD | Not started | - |
