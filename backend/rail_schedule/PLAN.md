# MBTA rail schedules: sources, workbook, and integration plan

This is the backend scheduling project's data/integration plan. Runnable tools and setup instructions are in [README.md](README.md).

## Delivery plan

The existing builder, single-departure lookup, and validator form the established baseline. `itinerary.py` now begins network/geometry and evaluation work. The packages below are the **delivery/verification checklist**, not a claim that those prototype capabilities have passed their completion checks. They replace the old generic phase numbering for backend work; detailed source/semantic notes follow this section.

### B1 — Editor-facing data contract (next)

**Depends on:** the existing generated exports; coordinate with frontend F1.

- [ ] Specify the station/platform, route, service-date, departure, source-manifest, and ruleset references the editor needs.
- [ ] Preserve original IDs, stop sequence, boarding/alighting restrictions, service-day times, and scheduled/estimated labels. Keep a draft rehearsal inventory separate from the official required list.
- [ ] Decide which existing exports can be consumed directly and which normalized additions are needed; document versioning and compatibility expectations.
- [ ] Choose a small worked example from a pinned dataset, including a branch/destination choice.

**Done when:** the frontend can consume a documented sample with explicit fields and dataset identity; missing/unsupported dates and schema mismatches have defined outcomes. This does not require choosing a production server framework.

### B2 — Directed network and transfer data

**Depends on:** B1. Supplies frontend F3's ride alternatives and connectivity checks.

- [ ] Derive directed ride patterns from consecutive stops on real trips, retaining shared trunks, branch choices, and intermediate calls.
- [ ] Preserve station/boarding-stop identity and import directed transfer/pathway constraints where available.
- [ ] Record entrance, exit, walking, and connection-buffer assumptions with provenance when they are not supplied or measured.
- [ ] Produce a reviewable connectivity/inventory report rather than inferring connections from map proximity.

**Done when:** representative Red/Green branch and interchange examples expand into valid explicit legs; unsupported transfers are visible; intermediate stops contribute coverage under the selected profile.

### B3 — End-to-end timetable evaluator

**Depends on:** B1 and B2. Integrates with frontend F4.

- [ ] Accept a date/start time and ordered legs, then select feasible boardable departures while retaining same-trip continuity.
- [ ] Include transfer/foot costs and recompute all later departures after an edit or missed connection.
- [ ] Respect calendars, exceptions, platform restrictions, overnight service-day times, and unavailable service.
- [ ] Return leg-level timing, elapsed totals, coverage facts, assumptions, and infeasibility reasons using the B1 contract.

**Done when:** a ride → foot/transfer → ride example evaluates correctly, lengthening the middle leg selects a later train or reports infeasibility, and midnight/calendar/terminal cases have meaningful checks. Keep official clock-boundary allowances separate from timetable fields.

### B4 — Silver Line extension

**Depends on:** a working rail contract/evaluator and a reviewed Silver route/stop inventory.

- [x] Include explicitly selected Silver routes (741 SL1, 742 SL2, 743 SL3, 746 SLW, 749 SL5, 751 SL4) and direction-specific boarding stops; street stops without a GTFS parent are grouped into `silver-*` stations with their stop IDs exported (`Stations.Stop IDs`).
- [ ] Extend calendar/timing/coverage checks and preserve existing rail-only scenarios.
- [x] Keep required inventory and unresolved Silver-specific rule interpretations explicit: Silver stations carry `Kind = silver`, the evaluator reports `silver_covered`/`silver_missing` separately from the 125-station rail set, and the coverage label says the Silver visit rule still needs clarification.

**Done when:** rail-only rehearsal and rail-plus-Silver profiles use the same evaluator without silently changing their coverage definitions. Full-record completeness also requires reconciling the supplied station-list attachment.

### Backend/frontend handoff

The backend owns transit identity, connectivity, schedule feasibility, and source provenance. The frontend owns editing, map interactions, and scenario presentation. F1 establishes their exchange contract with B1; B2 enables connected ride alternatives, and B3 enables realistic whole-itinerary timing. The delivery mechanism (files, worker boundary, or backend endpoint) remains an implementation choice, not an existing API.

## Deliverable and confirmed scope

The existing workbook covers core rail and all service dates in its published snapshot: **Red, Mattapan, Orange, Blue, Green-B, Green-C, Green-D, Green-E**. The export now also carries the six Silver Line routes as `kind = silver` stations and patterns; other buses, replacement shuttle buses, Commuter Rail, and ferries are excluded. The supplied record rules are documented separately; the official station-list attachment and certain Silver-specific interpretations remain outstanding.

**Future product scope:** Silver Line support is requested for later delivery; the supplied [Guinness rules](../../docs/references/GUINNESS-RULES.md) require it for the full attempt. The existing workbook remains a rail-only snapshot. Old Phase 7 numbering belongs to the archived proposal, not a current backend execution queue.

The downloaded snapshot is **Fall 2026, version D**, published **2026-10-21 20:52:18 UTC**, covering **2026-10-14 through 2026-12-12 inclusive**. Its hash, build timestamp, and record counts are recorded in `output/manifest.json`. Regeneration uses the new feed's published coverage rather than assuming these dates persist.

The workbook is `output/MBTA_Rail_Scheduling.xlsx` (about 19 MiB). Each data sheet also has an equivalent UTF-8 `.csv.gz` in `output/`, suitable for importing into a database. These generated artifacts are intentionally ignored by Git.

## What “exact wait” means

Three different quantities must remain distinct:

1. **Scheduled gap:** the difference between consecutive usable scheduled departures. This can be calculated to the second from the feed.
2. **Scheduled passenger wait:** the next usable scheduled departure minus the passenger's platform-arrival time. The workbook and CLI calculate this for a selected service day and destination.
3. **Predicted wait:** an updated estimate from `/predictions`, evaluated against current time or platform readiness. It can change. Actual wait is observed only after boarding.

Every rail stop time in this particular feed is marked **`timepoint=0`**, meaning estimated/non-timepoint. Published seconds do not imply that a train is obligated to appear at exactly that second. Even a timepoint marked exact by GTFS would be a schedule, not a guarantee of actual operation. Do not substitute a route's median headway or half-headway for a passenger-specific wait.

## Workbook guide

| Sheet | Purpose |
|---|---|
| Read me | Definitions, coverage, refresh instructions, and service-day conventions |
| Service calendar | Every date × route, active service IDs, actual timetable profile, holiday name, and exception counts |
| Profiles | 52 unique route/service-set combinations and their applicable date ranges; consult the calendar for the actual individual dates |
| Station hours | 20,820 daily station/route/direction rows, including no-service and arrival-only rows |
| Destination hours | 2,417 profile/station/direction/headsign summaries, retaining branches and short turns |
| Departures | 260,431 stop calls with arrival and departure service times, board/alight flags, platform and trip IDs, sequence, and route/destination gaps |
| Stations | 125 distinct rail parent stations, routes, geographic coordinates, and raw wheelchair-boarding codes |
| Calendar exceptions | 88 rail additions/removals from `calendar_dates.txt` |
| Holidays | Published holiday/date/route assignments and explicit flags for later holidays outside the feed |
| Alerts snapshot | Service notices retrieved at build time, with active periods and affected entities |
| Wait lookup | Editable next-departure and scheduled-wait calculator; Excel 2019+/365 `MINIFS` support required |

### How to use it

1. Open **Station hours** and filter a service date, station, route, and direction. Arrival times describe train calls; boarding times exclude terminal arrival-only calls. They are not station-door opening or closing times.
2. For a particular branch or short-turn destination, find the row's profile ID and filter **Destination hours**. On the Red trunk, “any southbound train” and “a train to Ashmont” have different waits.
3. For every trip time, join the date/route's **Service calendar** profile ID to **Departures**. Repeated days reference the same full timetable instead of duplicating millions of identical rows.
4. In **Wait lookup**, edit the yellow cells. Use an exact headsign from Destination hours, or leave destination blank to accept any train on the selected route/direction. A platform-specific CLI filter is also available with `--stop`.

The calculator searches the **selected service day only**. “No more matching departures” is distinct from the next morning's service. For an overnight request, choose the appropriate service day and use `24+` hours. If the next service day is needed, query it separately and calculate elapsed time from the absolute timestamps; do not subtract unanchored clock times across dates.

### Example: Park Street, Red southbound

These times combine Ashmont and Braintree trains; they are scheduled estimates.

| Service date | Pattern | First boarding | Last boarding |
|---|---|---|---|
| Thu Oct 22, 2026 | Monday–Thursday | 05:31:00 | 24:46:00 |
| Fri Oct 23, 2026 | Friday | 05:31:00 | 25:45:00 |
| Sat Oct 24, 2026 | Saturday | 05:32:00 | 25:46:00 |
| Sun Oct 25, 2026 | Sunday | 06:17:00 | 24:46:00 |
| Thu Nov 26, 2026 | Thanksgiving | 06:17:00 | 24:46:00 |

`25:45:00` means 1:45 AM on the following civil date, still belonging to the listed service day. For example, entering October 22 at 08:00:00, Park Street, Red, direction 0, destination Ashmont yields an **08:08:00 scheduled departure and an 8-minute scheduled wait**.

## Recommended data architecture

### Bulk schedules: official GTFS

Download <https://cdn.mbta.com/MBTA_GTFS.zip>. No API key is needed. This is the efficient source for a complete network-wide spreadsheet and date calendar.

Read:

- `feed_info.txt`: feed coverage/version and publisher timestamp.
- `routes.txt`, `lines.txt`, `directions.txt`: modes, line/branch membership, direction labels.
- `stops.txt`: parent stations and individual platform IDs.
- `trips.txt`, `stop_times.txt`: route/service/trip identity, stop sequence, headsign, arrivals, departures, and boarding restrictions.
- `calendar.txt` **and** `calendar_dates.txt`: base weekly operation plus explicit additions/removals. Do not activate canonical/non-operating services just because their trips appear in the feed.
- `calendar_attributes.txt`: human-readable descriptions; weekday flags and exception dates remain the scheduling authority.
- `transfers.txt` and `pathways.txt`: future itinerary evaluation's directed platform/transfer constraints, retaining minimum walk/wheelchair/buffer fields independently. No transfer graph is implemented in the workbook.
- `multi_route_trips.txt` and `trip_route_type`: detect aliases and replacement service. In this snapshot 1,577 bus trips are related to Green-B; they must not become rail departures.

The build currently rejects rail frequency service, incomplete rail times, conditional boardings, or multi-route rail services needing additional interpretation, rather than silently manufacturing exact departures. All are absent in this snapshot. Bus aliases are explicitly excluded.

Keep geographic coordinates, schematic display coordinates, and routing durations in separate fields. Preserve platform IDs even when station-hour summaries aggregate the parent station. Future transfer records must stay directed; never assume the reverse transfer has the same walk time or is permitted.

### Operational queries: MBTA V3 API

Base URL: <https://api-v3.mbta.com>. JSON:API responses contain `data`, optional `included`, and pagination links. Always follow `links.next`; do not assume one page is the entire timetable.

Useful calls (query values shown unescaped for readability):

```text
# Rail route inventory; includes Mattapan as light rail
GET /routes?filter[type]=0,1

# Station/platform hierarchy
GET /stops/place-pktrm?include=child_stops

# Scheduled Park Street southbound Red service for a specific service date
GET /schedules?filter[route]=Red&filter[route_type]=0,1&filter[stop]=place-pktrm&filter[direction_id]=0&filter[date]=2026-10-22&include=trip,stop&sort=departure_time&page[limit]=1000

# Narrow a post-midnight part of the same service day
GET /schedules?filter[route]=Red&filter[stop]=place-pktrm&filter[date]=2026-10-23&filter[min_time]=24:00&filter[max_time]=27:00

# Near-term live estimates; no full-future-timetable promise
GET /predictions?filter[route]=Red&filter[route_type]=0,1&filter[stop]=place-pktrm&filter[direction_id]=0&include=trip,stop,route

# Relevant disruptions along the entire line, not just the origin station
GET /alerts?filter[route]=Red

# Available service descriptions/calendar information
GET /services?filter[route]=Red
```

For first/last boarding, consider **all stop calls at that station**, filter unusable departures, then take min/max. Querying only a route's first/last stop sequences does not calculate first/last service at every intermediate station.

For live waits:

1. Restrict to rail mode and verify the trip's effective mode; route aliases alone are insufficient.
2. Match the chosen direction, actual platform, and required destination/reachable stop sequence.
3. Exclude cancelled/skipped/non-revenue calls. A prediction with no departure time is not a boarding opportunity. Do not replace a null departure with an arrival time at a terminal.
4. Use `trip_headsign` overrides when present; retain the scheduled headsign separately.
5. Match scheduled and predicted events by trip ID + stop ID + stop sequence, not just station name.
6. Retain `schedule_relationship`, uncertainty, retrieval timestamp, and relevant alert periods. Added/unscheduled trains can have no matching scheduled event; missing predictions do not prove no service.
7. Compute `predicted_departure_timestamp - platform_ready_timestamp`, not simply departure minus the time a route was first planned. Keep walk/transfer readiness separate.

MBTA says predictions update approximately every 12 seconds. A reasonable application design is a single shared backend cache with roughly 15-second prediction refreshes, and less frequent alert refreshes, or authenticated streaming. The spreadsheet is a static snapshot and has no live connection.

### API access and caching

The documented limits are **20 requests/minute without a key** and **1,000/minute with a free key**. Request a key at <https://api-v3.mbta.com/> for application use; pass it as `x-api-key` from local/backend configuration. The workbook build already works without one. `build_schedule.py` optionally reads `MBTA_API_KEY` from the local environment; it does not save the value.

Respect rate-limit headers and retry 429/transient server responses with backoff. Use `Last-Modified` / `If-Modified-Since` when applicable; MBTA notes included resources are not independently tracked by that cache header. Use pagination, sparse fields, and shared requests instead of fetching separately for each map marker.

## Holiday rules and publication boundaries

No universal holiday-to-Sunday rule is correct. The actual feed assigns:

- **Veterans Day, November 11:** regular Monday–Thursday service for the core rail routes in this snapshot. Other modes have exceptions.
- **Thanksgiving, November 26:** holiday/Sunday service for these rail routes.
- **November 27:** date-specific patterns differ by route. For example, Red uses Saturday service while Mattapan retains Friday service. Read each route's actual service calendar row.
- **Christmas Eve/Day and New Year's Eve/Day:** outside this feed; the spreadsheet flags the dates but provides no fabricated train times.

The official holiday webpage retrieved October 21, 2026 still says to check back for Thanksgiving/Christmas/New Year details. The GTFS already contains Thanksgiving service; use it as the current published timetable and refresh it as announcements change. The page's older October 12 notice also demonstrates why a Saturday schedule does not necessarily imply Saturday late-night service.

DST ends November 1, 2026, within this feed. Preserve original service seconds. For absolute timestamps use the GTFS **local noon minus 12 elapsed hours** origin in `America/New_York`, then add service seconds. The CLI implements this instead of assuming a fixed UTC offset or a 24-hour civil day.

## Refresh and validation

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/rail_schedule/requirements.txt
.venv/bin/python -m backend.rail_schedule.build_schedule
.venv/bin/python -m backend.rail_schedule.validate_schedule --gtfs data/MBTA_GTFS.zip
```

For an existing ZIP, supply `--gtfs /path/to/MBTA_GTFS.zip`. Without `--gtfs`, the build downloads a new snapshot to `data/MBTA_GTFS.zip`. Every build also preserves the ZIP in `data/raw/MBTA_GTFS_<hash-prefix>.zip`; the precise path is recorded in the manifest's `local_archive` field. The current pinned file is `data/raw/MBTA_GTFS_97aecc9ed3980544.zip`. Validate against that archived ZIP to reproduce this audit after a newer upstream feed appears. Local feed archives are ignored by Git.

The current `output/validation.json` records:

- 480 date/route assignments independently reconstructed from raw service calendars and exceptions.
- All 260,431 exported stop events matched against the raw GTFS by trip/platform/sequence/times/boarding flags.
- All 20,820 daily station summaries checked; branch summaries and route/destination gaps checked.
- 246 station/direction/date rows with no scheduled rail and 1,024 arrival-only rows retained explicitly.
- Workbook sheet dimensions and the wait calculator's saved sample result checked.
- 530 scheduled departures matched to public API trip/platform/sequence identities and timestamps: regular Red weekday, Blue Thanksgiving, and Green-E Friday including late-night service.

Excel formula recalculation was not executed in this environment; the formula's cached sample and independent CLI output agree. Public API checks are dated spot checks and can diverge after a new upstream feed is published. Use `--skip-api` for an offline raw-feed audit, not as a substitute for resolving a newly discovered mismatch.

For future application use, download/check the feed daily, regenerate when its hash changes, diff station/service inventories before adopting it, and refresh again before the selected attempt date. The next product milestone remains the manual map-and-itinerary editor; these timetables provide validated inputs for the later evaluator, not a proven optimal route.

## Primary sources

- [MBTA GTFS download and overview](https://www.mbta.com/developers/gtfs)
- [Official GTFS ZIP](https://cdn.mbta.com/MBTA_GTFS.zip)
- [MBTA V3 API overview](https://www.mbta.com/developers/v3-api)
- [Live API documentation](https://api-v3.mbta.com/docs/swagger/index.html)
- [Machine-readable API specification](https://api-v3.mbta.com/docs/swagger/swagger.json)
- [MBTA V3 best practices, rate limits, caching, and predictions](https://www.mbta.com/developers/v3-api/best-practices)
- [MBTA holiday service announcements](https://www.mbta.com/holidays)
- [GTFS Schedule reference: calendars, boarding rules, timepoints, and service time](https://gtfs.org/documentation/schedule/reference/)
- [MBTA GTFS extensions](https://github.com/mbta/gtfs-documentation/blob/master/reference/gtfs.md)
