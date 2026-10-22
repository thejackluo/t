# Map editor frontend project

**Status:** requirements captured; implementation has not started.

**Responsibility:** the Boston-centered Google Maps workspace for drawing and revising a connected itinerary, viewing timing and station coverage, and comparing route ideas.

The canonical project plan is [REQUIREMENTS.md](REQUIREMENTS.md). It contains confirmed user decisions, clearly labelled proposed defaults, delivery steps, and acceptance criteria; there is no separate competing roadmap.

The [interactive-map design overview](../../docs/INTERACTIVE-MAP-PLAN.md) provides the wider architecture and brainstorming context.

## Inputs and boundaries

- [Rail schedule backend](../../backend/rail_schedule/README.md): published departures, stop/trip identities, calendars, and future itinerary evaluation.
- [Guinness reference](../../docs/references/GUINNESS-RULES.md): qualifying visits, clock boundaries, allowed transfers, and full-attempt coverage.
- Google Maps canvas with application-owned MBTA station handles and ride/foot segments.
- The [schedule explorer](../../utilities/schedule_explorer/README.md) is a separate inspection utility, not the map-editor frontend.

## Build order

1. Reuse the schedule data and establish directed ride/transfer records plus the required-station inventory.
2. Render the Google map, transit context, and selectable MBTA stations.
3. Add connected Ride/Run editing, route alternatives, transfers, editable foot paths, and undo.
4. Evaluate timing and coverage; show missed-connection consequences and save/reload scenarios.
5. Later: optimization, attempt-day tools, and Silver Line integration.

Silver Line is required for full-record coverage even though implementation is deferred. A rail-only plan is a rehearsal. The station-list attachment and evidence guide referenced by the supplied rules are still needed; map implementation also needs local Google Maps configuration.
