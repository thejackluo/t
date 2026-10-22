# Research notes and source register

> Archived research snapshot. Findings and versions describe the original investigation, not a fresh verification.

Research date: 2026-10-21 (workspace date). Web services may report UTC timestamps on the following day. These are planning observations, not an attempt-date data snapshot.

## 1. Get Shit Done installation

- [Original repository](https://github.com/gsd-build/get-shit-done): GitHub reports `archived: true`; its current README directs users to GSD Core.
- [Maintained successor](https://github.com/open-gsd/gsd-core): supports OpenCode through a runtime-aware installer.
- [Installation guide](https://github.com/open-gsd/gsd-core/blob/main/docs/how-to/install-on-your-runtime.md): describes local installation, commands, plugin, agents, and restart requirements.
- npm metadata verified for `@opengsd/gsd-core@1.18.0`: requires Node >=24 and npm >=10. Local bootstrap uses Node 24.22.1; the workspace initially had Node 22.18.0.
- Installed locally into `.opencode/`; runtime marker and version file identify OpenCode and 1.18.0. Installer also reported managing `resolve_model_ids` and `runtime` preferences in `~/.gsd/defaults.json`.
- Pin both the installer and MCP launcher. Reinstall with `node scripts/install-gsd.mjs`.

## 2. Official MBTA data

| Source | Use | Notes |
|--------|-----|-------|
| [GTFS overview](https://www.mbta.com/developers/gtfs) | Bulk topology and scheduled services | MBTA recommends checking for updates daily |
| [GTFS ZIP](https://cdn.mbta.com/MBTA_GTFS.zip) | Reproducible source snapshot | Save checksum, retrieval time, feed validity and service dates |
| [V3 API overview](https://www.mbta.com/developers/v3-api) | Stops, routes, patterns, schedules, predictions, alerts | JSON:API; resource relationships and endpoint-specific filters |
| [V3 reference](https://api-v3.mbta.com/docs/swagger/index.html) | Exact request and response contracts | Check during implementation; include pagination and error handling |
| [GTFS realtime](https://www.mbta.com/developers/gtfs-realtime) | Optional live trip context | Not a replacement for future-date static schedules |
| [Maps](https://www.mbta.com/maps) | Visual reference and layout review | Stable subway reference: https://www.mbta.com/subway-map |
| [Green Line Extension](https://www.mbta.com/projects/green-line-extension-glx) | Review post-2022 station scope | Network changes make historical station totals unsuitable |
| [MassDOT data license](https://cdn.mbta.com/sites/default/files/2023-08/mbta-massdot-develop-license-agreement.pdf) | Data-use terms | Linked by MBTA; review when distributing data/assets |

The V3 overview documents a subway route filter of `filter[type]=0,1`. A live read of [that query](https://api-v3.mbta.com/routes?filter%5Btype%5D=0,1) returned:

| Route ID | Route name |
|----------|------------|
| Red | Red Line |
| Mattapan | Mattapan Line |
| Orange | Orange Line |
| Green-B | Green Line B |
| Green-C | Green Line C |
| Green-D | Green Line D |
| Green-E | Green Line E |
| Blue | Blue Line |

This confirms initial route IDs, not a final station count or attempt-day service. Silver Line is not included by this rail-mode filter and requires an explicit challenge profile.

MBTA recommends requesting a free API key early. Its V3 page documents a default 1,000 requests/minute with a valid key and key requirements for streaming/version control. Implement caching and honor actual API responses rather than building around a fixed quota. Live integration should use a small server-side proxy if keeping the key private.

## 3. Guinness category status

Primary source: [Fastest time to travel to all Boston subway train stations (pre 2022)](https://www.guinnessworldrecords.com/world-records/405906-fastest-time-to-travel-to-all-boston-subway-stations).

The public page is explicitly titled **pre 2022** and says **“This record is currently inactive and no applications are being accepted for it.”**

Consequences for product planning:

1. Do not label an itinerary “Guinness compliant” based on this public page.
2. Keep category ID, rules version, required station inventory, and benchmark provenance in the scenario.
3. Ask the team to confirm a current applicable category and obtain its detailed guidelines.
4. A self-defined contemporary all-stations challenge can still be planned while this is unresolved.

A current replacement category, authoritative current benchmark, station count, visit predicate, walking/alternate-transport allowances, and evidence requirements were **not verified**. Historical news reports and community speedruns may use different networks or scope; no historical time has been adopted as the project's target.

## 4. What still needs empirical research

- Exact active station set and trip patterns for the selected service date.
- Platform-to-platform transfer times, including exits and fare-control effects.
- Terminal turnaround and same-vehicle continuation behavior.
- Candidate walking shortcuts, validated on the ground and permitted by the chosen rules.
- Closure/shuttle impacts and missed-connection sensitivity.
- Actual versus scheduled trip times from rehearsals.

This research task did not download a GTFS feed or measure transfers. A separate `build_schedule.py` workbook tool and generated `output/` files appeared during setup; their completeness and provenance should be reviewed in Phase 1 before adopting them. Measured transfer data remains a rehearsal deliverable.
