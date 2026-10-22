# Map editor frontend project

**Status:** requirements captured; early local-server prototype work is in progress. The end-to-end editor milestone is not yet verified.

**Responsibility:** the Boston-centered Google Maps workspace for drawing and revising a connected itinerary, viewing timing and station coverage, and comparing route ideas.

- [REQUIREMENTS.md](REQUIREMENTS.md) defines **what** the editor should do: confirmed user decisions, proposed defaults, and acceptance behavior.
- [PLAN.md](PLAN.md) breaks down **how to deliver it**: F1–F5 work packages, backend dependencies, and completion checks. None is marked verified-complete by this documentation update.

`server.py` begins the local editor server and integrates the backend itinerary prototype. Treat it as ongoing implementation rather than a validated replacement for the working schedule explorer.

The [interactive-map design overview](../../docs/INTERACTIVE-MAP-PLAN.md) provides the wider architecture and brainstorming context.

## Inputs and boundaries

- [Rail schedule backend](../../backend/rail_schedule/README.md): published departures, stop/trip identities, calendars, and future itinerary evaluation.
- [Guinness reference](../../docs/references/GUINNESS-RULES.md): qualifying visits, clock boundaries, allowed transfers, and full-attempt coverage.
- Google Maps canvas with application-owned MBTA station handles and ride/foot segments.
- The [schedule explorer](../../utilities/schedule_explorer/README.md) is a separate inspection utility, not the map-editor frontend.

## Delivery at a glance

| Package | Result | Dependency |
|---------|--------|------------|
| F1 | Agreed input/scenario model and one worked example | Backend B1 |
| F2 | Google map and selectable MBTA stations | F1 station input; local map configuration |
| F3 | Connected Ride/Run itinerary with explicit transfers and undo | F1/F2 and backend B2 |
| F4 | Feasible whole-itinerary timing and coverage | F3 and backend B3 |
| F5 | Saved/reloaded candidates and useful comparison | F3 scenario model; F4 for evaluated comparison |

The first useful editor milestone is F1–F5 working together on a **rail rehearsal**. Saving can be developed alongside timing once the scenario model is stable. Optimization, attempt-day tools, and Silver integration follow later.

Silver Line is required for full-record coverage even though implementation is deferred. A rail-only plan is a rehearsal. The station-list attachment and evidence guide referenced by the supplied rules are still needed; map implementation also needs local Google Maps configuration.
