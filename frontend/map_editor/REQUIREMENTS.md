# First application: Google Maps segment planner

**Status:** requirements discussion captured on 2026-10-21; early prototype implementation is in progress. Delivery/completion checks are tracked separately in PLAN.md.

This document records the current discussion and supplies the authoritative frontend decisions alongside the broader [design overview](../../docs/INTERACTIVE-MAP-PLAN.md). Google Maps supersedes the earlier schematic-first option. The earlier roadmap is archived reference material, not an active execution plan. The sequence below is a proposed first-application plan, not completed work.

For task breakdown, dependencies, and completion checks, use [PLAN.md](PLAN.md). This document defines expected behavior; the plan defines how to deliver it.

## Goal

Build a Boston-centered Google Maps workspace where the team can create and revise a connected journey using rail rides and outdoor running/walking links, then see the scheduled/estimated elapsed time and station coverage. Use the existing rail schedule backend's artifacts as inputs. Manual experimentation comes before automatic all-stations optimization.

## Confirmed in discussion

| Area | Decision |
|---|---|
| Primary canvas | Google Map with native transit overlay; use official MBTA identities for selectable stations and itinerary paths. |
| Drag gesture | Choose Ride or Run before dragging from station A to station B. Station coordinates stay fixed; dragging creates a connection. Also provide endpoint selection without dragging. |
| Ambiguous/cross-line rides | Preview plausible rail paths, including explicit transfers; the user selects one. Expand it into ride and transfer legs rather than drawing a fictitious direct train. |
| Running geometry | Suggest a pedestrian street route and allow editable waypoints; calculate distance from that path and time from running pace. |
| Route construction | One connected ordered itinerary. First segment establishes the start; subsequent segments extend the endpoint. Allow insertion/replacement, reordering, deletion, and undo; surface disconnected edits. |
| Initial rail scope | Red, Orange, Blue, Green-B/C/D/E, and Mattapan, matching the current schedule dataset. |
| Foot links | Running, walking, and internal station transfers are supported. Foot travel alone ordinarily does not earn station coverage. |
| Endpoints | Free choice of start/end, with optional pins. No assumed return-to-start requirement. |
| Coverage | A ridden normal-service train stopping at a station contributes planned coverage, including intermediate calls; actual claim coverage is separate. |
| Full record scope | The subsequently supplied Guinness text requires Silver Line. Retain later delivery, but never label rail-only completion as full-record completion. Exact required inventory awaits the referenced image. |

## Recommended defaults: not yet confirmed product choices

The user asked to avoid an extended questionnaire after supplying the guidelines. These are explicit proposals, not additional user decisions:

- **Screen:** large map plus a chronological itinerary and persistent coverage/time summary; date/start-time and save controls above it. Desktop-first planning with a usable narrower layout.
- **Date:** require a service date and start time for evaluated results. Keep them editable; do not claim a date outside the imported feed has a timetable. No attempt date or default clock time is fixed yet.
- **Train timing:** evaluate actual feasible departures using the selected trip's stop sequence, boarding/alighting permissions, branch, direction, and platform. Keep a continuous same-train ride continuous; do not add a wait at every intermediate stop.
- **Foot timing:** configurable running pace, walking pace, entrance/exit times, directed platform-transfer costs, and optional connection buffers. No pace or station-specific cost has been validated yet. Label placeholder costs as assumptions.
- **Recalculation:** when an earlier leg changes, recompute the remaining itinerary. A missed train leads to the next feasible departure or an unavailable result, rather than retaining an impossible boarding.
- **Manual adjustments:** retain their reason, source, and timing type; distinguish a manually estimated segment from a timetable-backed one.
- **Saving:** named local candidate scenarios, duplication, portable JSON import/export, and a CSV itinerary. Save order, geometry, selected services, assumptions, dataset/ruleset references, date/time, and endpoint pins. Proposed comparison shows time, coverage, running distance, transfers, and fragile connections for two candidates.
- **Live data and shared editing:** later additions; not necessary to evaluate a saved schedule-based rehearsal.

## Segment and event model

Store explicit **ride, run, walk, internal transfer, wait, and break** legs. An exterior foot link can additionally have station exit and entry subcosts so these are not hidden inside train waits or counted twice.

Each leg needs stable IDs, ordered position, mode, origin/destination station and platform/entrance references where applicable, geometry source, distance when meaningful, duration components, notes, and provenance. Rail rides retain route/trip/service/date/direction and the intermediate stop calls; connected trip continuity must survive visual editing.

Every time value must identify whether it is **scheduled**, **estimated**, **predicted**, or **observed**, plus its source. The itinerary should expose scheduled boarding/arrival, wait, ride, run/walk, access/transfer, break, and cumulative elapsed columns without double-counting components.

For record planning, time begins at first-train doors closing and ends at final-platform footfall. Pre-start wait/access is preparation. Schedule times are proxies for those physical events; keep estimated boundary allowances explicit. All intervening breaks count. Do not display centisecond forecast precision as if it were measured evidence.

Keep coverage entities separate from routing platforms and entrances. A scenario's required station list comes from its versioned ruleset; the imported rail station count is not itself the official inventory. See [the Guinness reference](../../docs/references/GUINNESS-RULES.md) for closure exceptions and unresolved Silver/start-finish wording.

## Google Maps integration constraints

- The native `TransitLayer` supplies visual transit context. Its API does not expose per-route filters or a station topology for editing. Own MBTA markers/handles and route geometry provide stable IDs, hit targets, route selection, and coverage.
- “Boston-only” initially means Boston-centered map and selectable MBTA inventory. Native transit context can show other transport; line/mode filters apply to the application's own data. Do not promise that Google's transit overlay itself can be filtered to only these eight route IDs.
- Rail geometry follows MBTA shapes/stop sequences, not a street route or a straight station-to-station line.
- Pedestrian routing is a proposal requiring inspection, especially for station entrances and shortcuts. Keep entrance costs and manual geometry provenance visible; do not infer access from a parent-station center point.
- Google's old Drawing Library became unavailable in May 2026. Use supported editable overlays or an appropriate maintained drawing tool; do not plan around `DrawingManager`.
- Implementation needs a configured Google Maps project/browser key and any pedestrian-routing service configuration. Confirm current billing, quotas, and provider storage/display requirements when selecting the routing integration. Do not put credentials in planning documents.

Documentation checked during discussion:

- <https://developers.google.com/maps/documentation/javascript/trafficlayer>
- <https://developers.google.com/maps/documentation/javascript/reference/map#TransitLayer>
- <https://developers.google.com/maps/documentation/javascript/shapes>
- <https://developers.google.com/maps/documentation/javascript/examples/map-drawing-terradraw>

## Existing assets to reuse

- `backend/rail_schedule/build_schedule.py`: GTFS ingestion and workbook/data exports; review before adding a second importer.
- `backend/rail_schedule/schedule_lookup.py`: next scheduled boardable departure for a service date/platform-ready time. It is not yet a multi-leg route evaluator.
- `output/manifest.json`: pinned feed and artifact metadata. Current schedule coverage: 2026-10-14 through 2026-12-12; 125 rail parent stations, 52 profiles, and 260,431 exported departure-sheet rows. These generated files remain local/ignored.
- [Backend schedule plan](../../backend/rail_schedule/PLAN.md): calendar, branch, platform, overnight-service, and validation details. The workbook does not implement a transfer graph.

## Delivery sequence and acceptance

1. **Data/rules foundation:** reuse the schedule exports; produce directed ride/transfer records and a reviewable station inventory; attach the supplied rules with unresolved inventory/exception details visible.
2. **Google map canvas:** render the Boston map/transit context and own MBTA station handles. Select stations by pointer/keyboard without moving their geographic positions.
3. **Segment editor:** demonstrate a rail ride, a rail option requiring a transfer, and an editable outdoor foot link in one connected itinerary. Show intermediate stations and repeated traversals. Verify undo and disconnected-edit handling.
4. **Useful timed first application:** evaluate the itinerary against a chosen date/start time; show time breakdown/coverage, change an earlier foot leg enough to miss a train, and observe the next feasible service or an unavailable result. Save/reload preserves geometry, assumptions, and data/ruleset identity.
5. **Later roadmap work:** candidate optimization, attempt-day/offline/evidence support, and Silver integration. Until Silver and the approved inventory are implemented, record status remains partial even if the rail rehearsal is complete.

The historical roadmap split the foundation/map/editor/timing work into Phases 1–4. That archive is reference only; use the confirmed decisions here when preparing a new implementation plan. The first application should include useful timing before being called a completed map-and-itinerary deliverable.

## Minimal remaining inputs

1. The **station-list image attached to the Guinness guidelines**, to establish the actual required set.
2. The separate **Guide to Your Evidence**, before designing the later evidence workflow.
3. Before live-map implementation: local Google Maps configuration. Before evaluating an intended attempt: its service date/start time and a feed covering that date. These are editable scenario inputs, not reasons to continue the questionnaire now.
