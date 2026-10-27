# Route studio: run, create, and export

## Start

With **Python 3.11+**, the existing schedule exports, and their matching archived GTFS ZIP:

```sh
python3 -m frontend.map_editor.server
```

Open **http://127.0.0.1:8001**. No third-party Python or JavaScript packages are required. Defaults resolve from file locations, so direct invocation also works from another directory:

```sh
python3 /path/to/t/frontend/map_editor/server.py --port 8001
```

The server reads repository-level `output/manifest.json`, scheduling CSVs, and the archive named by its `local_archive` field. It verifies the archive hash before combining shapes and timetables. `--data` and `--gtfs` override these paths; an unmatched archive is rejected. Generate missing artifacts using the [backend guide](../../backend/rail_schedule/README.md).

## Create a route

1. Choose the service date and platform-ready time. `25:15` means 1:15 AM after the selected service date. Use a date within the imported coverage.
2. Choose **Ride**, then select endpoints with search/dropdowns, click station handles, or press on a station **or on its track** and drag along the line: the nearest station snaps under the pointer and the rail path previews live while you drag; release to keep it. Station positions stay fixed.
3. **Preview rail paths**, inspect alternatives, and **Add selected path to itinerary**. Rail paths use actual directed MBTA GTFS shapes, including intermediate stops. They do not use road directions or station-to-station chords.
4. Extend the current endpoint. **Replace**, move-up/down, **Delete**, **Undo**, and **Redo** revise the itinerary. Disconnected changes block subsequent timing and coverage until repaired.
5. Modes are **Auto**, **Ride**, and **Run**. Auto (the default, also used when you drag along a track) fetches the rail paths *and* a street run for the same station pair, times each one against your current itinerary with `/api/evaluate`, sorts them by predicted arrival and marks the fastest; every card states whether it is scheduled rail, estimated rail, or an estimated run, and you can still pick any of them. While dragging, the run is a straight-line estimate so Google is only asked once, on release. Walk is no longer offered for new connections (saved `walk` legs still load and evaluate at the walk pace). For **Run**, previewing already requests the street route when street routing is available (Google Maps connected in the browser, or `GOOGLE_ROUTES_API_KEY` configured on the server) the pedestrian street route is requested automatically and Google's own walking estimate is shown beside the pace-based time; otherwise the connection stays a clearly labelled straight-line sketch. Choose **Edit foot path** to refine it: in the preview, click to insert waypoints and drag interior purple handles; on Google Maps, use editable polyline handles. Coordinates can also be edited directly. **Suggest streets** re-requests the route; **Reset sketch** returns to a two-point user-owned sketch.
6. The evaluator chooses feasible trains for the selected pattern and date, preserving branches, platforms, trip/service IDs, stop permissions, intermediate calls, and same-train continuity. Changing an earlier foot path, pace, time, or transfer buffer recomputes downstream boardings. Hover any station-to-station piece of a rail path on the map to see its scheduled (or estimated) minutes and arrival; the segment card's **Intermediate stops** list shows the same per-stop times. Segments with no scheduled train are marked **estimated**, with the reason in the card.
7. **Save** stores a named candidate in this browser; **Duplicate** creates a new candidate. JSON import/export is portable and dataset-pinned. CSV exports the evaluated itinerary with original `24+` service times. Scenarios are not written to the repository.

The example button creates **Alewife → Park Street → Kenmore → Fenway**, including a real platform transfer and an outdoor running sketch to edit.

## Put routes into your Google My Maps project

Reference: [your Google My Maps project](https://www.google.com/maps/d/u/0/edit?mid=1uOrMD32-8alM_w2tyQ-Xio6b6jcxRyk).

1. Create the itinerary here and click **Export to My Maps**.
2. Open the Google My Maps project and sign in.
3. Choose **Add layer → Import**, then upload the downloaded KML.

Imported rail lines follow MBTA track shapes and retain ordered segment names and intermediate-stop descriptions. For a separate reference layer, download **[all MBTA rail tracks and stations](http://127.0.0.1:8001/api/export/network.kml)** from the running server or Help dialog.

My Maps does not automatically snap arbitrary hand-drawn lines to subway tracks. Generate rail paths in route studio and import their geometry. Moving/deleting their vertices inside My Maps can change that geometry. Export/import is manual; the editor does not sign into Google, modify the private project, or synchronize changes back from it. The supplied project redirected the test browser to Google sign-in, so import into the private project has not been verified.

## Connect the embedded Google Maps canvas

Choose **Connect Google Maps** for a step-by-step Google Cloud setup guide, paste a restricted browser key, and select **Load Google Maps**. With **Remember on this device** (default) the key is kept in this browser's local storage, so new tabs and reloads reconnect without asking; uncheck it to keep the key for the current tab only, and use **Forget saved key** to remove it. Keys never enter scenario saves/exports. The key's website restriction must include the origin you are actually using; the Help dialog shows the current page origin, e.g. `https://mbta-route-studio.vercel.app/*` for the Vercel deployment. To avoid the prompt entirely, configure the environment (on Vercel: Project → Settings → Environment Variables, then redeploy):

```sh
GOOGLE_MAPS_API_KEY="your-browser-key" python3 -m frontend.map_editor.server
```

Enable **Maps JavaScript API**, configure billing, and allow `http://127.0.0.1:8001/*` (and `http://localhost:8001/*` if used). Enable the current **Routes API** integration for **Suggest streets** on a foot segment; it uses `google.maps.routes.Route.computeRoutes` in walking mode. Google billing/quotas apply to provider-backed operations.

`TransitLayer` supplies background transit context. Application-owned station handles and MBTA shapes drive selection/editing; supported editable `Polyline`s are used rather than the retired Drawing Library.

Without a key, the clearly labelled **geographic track preview** supports route creation, foot editing, timing, and KML export. It is an own-data geographic view, not Google Maps or a street basemap. Authentication failure returns to that preview. The Google canvas was verified with a user-supplied restricted browser key; pedestrian street suggestions and private My Maps import still need live verification.

Google-derived pedestrian paths remain **session-only**. Autosave/JSON replace them with an explicitly labelled endpoint sketch; KML omits those foot paths. User-drawn foot geometry and MBTA rail geometry are saved/exported. Inspect pedestrian suggestions for entrances, crossings, and access: a station center is not a verified entrance.

## Timing, coverage, and current boundaries

- Times are **scheduled non-timepoint estimates**, not live predictions or observations. Display labels use America/New_York service hours; elapsed arithmetic preserves `24+` hours. The evaluator does not invent the next service day's timetable.
- **Plan duration** includes preparation from the platform-ready time. The first-train departure → last-train arrival proxy is separate. These are schedule proxies, not measured doors-closing/platform-footfall events or validated boundary allowances. Foot travel after the last ride is outside that rail-clock proxy.
- Transfers use **directed GTFS platform rules/pathways**, including trip-specific prohibitions and minimums. Park Street–Downtown Crossing passage transfers retain separate station IDs. Missing pathway walk time uses length / **1.2 m/s** as a provisional estimate. Minimum transfer time is a floor, not a second walk cost. Additional buffer defaults to **30 seconds**. A station with **no GTFS pathway data at all** (most surface Green Line stops) gets an explicitly estimated same-station platform change, **120 seconds** by default (`station_change` assumption); where GTFS pathways exist but do not connect two platforms, the transfer stays unavailable.
- When GTFS marks an in-station platform change as **not possible** (`transfer_type 3`, e.g. reversing direction at Copley, Boylston, Symphony, Kendall, Central, Wonderland) or its pathways do not connect the two platforms, the evaluator prices an explicitly **estimated street-level transfer** instead of refusing: platform → nearest GTFS entrance along the station's own pathways, a straight-line outdoor walk between entrances at 1.2 m/s, then entrance → platform. The card shows the entrances and outdoor metres; the forbidden directed edge is never used. Stations with no reachable entrance still return `transfer_not_permitted`.
- When no scheduled train fits, the segment is marked **unavailable** with a specific reason (`no_service_remaining` with the last scheduled departure, `transfer_not_permitted` with the platform IDs, `no_trips_for_profile`, or `outside_feed`). Timing continues downstream using the pattern's **typical (median) scheduled ride time**, labelled `estimated`; such segments add no planned coverage and never invent a trip.
- Station entry/exit defaults to **60 seconds each**, applied at necessary foot/rail boundaries. Consecutive foot links do not repeatedly enter/exit intermediate stations. Running defaults to **6 min/km**, walking to **12 min/km**. Two-point foot sketches are unverified straight-line estimates.
- Coverage derives from successfully evaluated ride calls, including intermediate stations. Foot-only visits and blocked/unavailable suffixes add no rail coverage. Failed legs leave totals for the feasible prefix only.
- Candidate search is bounded to **four rides and three displayed alternatives**, ranked by representative ride durations, a transfer penalty, and a penalty per repeated station. Same-line branch changes (Ashmont → JFK/UMass → Braintree) and repeated trunk traversals (Riverside → Heath Street) are allowed and labelled; far slower loops are dropped. The platform-ready time filters out paths whose service has already ended for the day. It is not an optimizer or proof of fastest travel; exact feasible departures are evaluated after selection.
- The rail inventory is a **rehearsal**, not the approved Guinness list. Silver Line, the official inventory, endpoint/boundary refinements, explicit break/manual-duration legs, calibrated entrance costs, endpoint pins, comparison views, optimization, and attempt-day tools remain further work.

## Local API and scenario contract

- `GET /api/network`: stable station IDs, coordinates, routes, track shapes, source manifest, available service dates, and rail-rehearsal ruleset.
- `GET /api/options?from=place-alfcl&to=place-aport&date=2026-10-22&time=08:00`: alternatives expanded into ride records with pattern/start/end indices, platform IDs, intermediate station IDs, and clipped shapes, plus `revisited_stations` and `estimated_transfers` flags. Optional `route=Red` constrains selection to one line; optional `time` drops paths with no service remaining.
- `POST /api/evaluate`: scenario object; returns canonical legs, scheduled trip/platform calls, per-station-pair `segments` (geometry plus scheduled or estimated seconds), separate wait/transfer/access events, feasible coverage, and component totals including `estimated_ride`. Blocked/unavailable legs retain explicit `status`, `reason_code`, and message; `summary.unavailable_legs` lists them.
- `POST /api/export/kml`: scenario → KML containing MBTA/user-owned path geometry.
- `GET /api/export/network.kml`: entire rail track/station reference layer.
- `GET /api/config`: local browser-key configuration, whether server-side street routing is available (`foot_routing`), and the user's My Maps URL. No browser key appears in scenario payloads.
- `GET /api/foot-route?from=place-kencl&to=place-fenwy`: server-side Google Routes API pedestrian route (requires `GOOGLE_ROUTES_API_KEY`, a server key restricted to the Routes API), returning station-anchored geometry, `provider_distance`, and `provider_seconds`. Google geometry remains session-only in saves/exports.

Saved JSON uses `schema: 1`, a stable scenario `id`, `name`, pinned dataset SHA-256, `ruleset: "rail-rehearsal-v1"`, `date`, service `time`, editable `assumptions`, and ordered `legs`. Ride legs retain `pattern`, `start`, and `end`; the backend reconstructs their authoritative platforms, stations, and geometry. Foot legs retain mode, fixed station endpoints, user points, and geometry provenance. JSON imports reject incompatible dataset/ruleset/schema identities and are recomputed.

## Verification

```sh
python3 -m unittest backend.rail_schedule.test_itinerary frontend.map_editor.test_server utilities.schedule_explorer.test_explore
node --check frontend/map_editor/static/app.js
node --check frontend/map_editor/static/map.js
```

Tests cover shape geometry, destination-specific waits against the existing lookup, cross-line and directed/trip-specific transfers, same-train continuity, missed trains after foot-time changes, disconnected coverage, overnight/unpublished service, KML coordinates, and HTTP delivery. They require the generated snapshot/archive; a skip is not validation. Browser checks cover the own-data preview, route workflow, and live Google canvas (track/station alignment, map-handle selection, reload reconnection from session storage). Pedestrian street suggestions and KML import into the private My Maps project still need live verification; the operator-supplied key was never stored in the repository or scenarios.
