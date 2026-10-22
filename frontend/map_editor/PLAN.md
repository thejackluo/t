# Map editor delivery plan

**Status:** delivery breakdown for implementation in progress. A local-server prototype exists in `server.py`; none of F1–F5 has been verified complete by this documentation update.

[REQUIREMENTS.md](REQUIREMENTS.md) remains the authority for expected behavior and the distinction between confirmed decisions and proposed defaults. This plan sequences that work; the [design overview](../../docs/INTERACTIVE-MAP-PLAN.md) explains the wider ideas.

## First useful milestone

Create a connected rail-rehearsal itinerary on Google Maps, edit a running/transfer leg, see the resulting train and time changes, save/reload the scenario, and compare two candidates with explicit station coverage.

Do not describe a drawn route as feasible until it has been evaluated, or a rail rehearsal as full Guinness coverage. Automatic optimization is a later milestone.

## F1 — Contract and scenario model (next)

**Depends on:** backend [B1](../../backend/rail_schedule/PLAN.md#b1--editor-facing-data-contract-next); work together on the same example.

- [ ] Identify the station/boarding-stop, route, departure, source-manifest, and ruleset fields the editor consumes.
- [ ] Define ordered ride, run, walk, transfer, wait, and break legs with stable IDs and provenance.
- [ ] Include service date/start time, endpoint pins, geometry, timing assumptions, and dataset/ruleset identity in the scenario.
- [ ] Define visible states for disconnected routes, unavailable data, estimated timing, and partial coverage.

**Done when:** one documented ride → foot/transfer → ride scenario can be represented without losing platforms, intermediate calls, or assumptions. The example may be untimed before B3, but must be labelled accordingly.

## F2 — Google map and station selection

**Depends on:** F1's station contract and local Google Maps configuration. The map shell can proceed while B2/B3 are developed.

- [ ] Create the frontend shell and Google Maps canvas with transit context.
- [ ] Render application-owned MBTA station handles using official identities and geographic coordinates.
- [ ] Add station search/details and pointer/keyboard endpoint selection.
- [ ] Keep route filters and hit targets on the application's own data; station positions remain fixed.

**Done when:** the user can find/select two rail stations and inspect their identities on the map, including in a narrower layout. Selecting a station does not invent a direct train between it and another station.

## F3 — Connected itinerary editing

**Depends on:** F1/F2 and backend [B2](../../backend/rail_schedule/PLAN.md#b2--directed-network-and-transfer-data).

- [ ] Choose Ride/Run before dragging; also support endpoint selection without dragging.
- [ ] Preview valid rail alternatives and expand the selected option into explicit rides/transfers with intermediate calls.
- [ ] Suggest a pedestrian street path with editable waypoints and configurable pace assumptions.
- [ ] Support extending, inserting/replacing, reordering, deleting, and undoing legs; flag disconnected edits.

**Done when:** a direct ride, a ride needing a train change, and an outdoor foot connection can be edited in one ordered itinerary. Repeated/missing stations are visible; foot travel alone does not earn an ordinary ride visit. Before F4, any time estimates remain visibly provisional.

## F4 — Scheduled timing and coverage

**Depends on:** F3 and backend [B3](../../backend/rail_schedule/PLAN.md#b3--end-to-end-timetable-evaluator).

- [ ] Evaluate the whole itinerary for the chosen service date/start time, retaining service/trip/platform references.
- [ ] Show wait, ride, run/walk, access/transfer, break, and cumulative totals without double-counting.
- [ ] Re-evaluate downstream legs after edits; explain missed connections and infeasible journeys.
- [ ] Separate planned coverage from observed attempt facts and show rule/assumption provenance.

**Done when:** increasing a foot leg changes the next feasible train or produces an unavailable result; unsupported dates yield no invented timetable; required/missing station totals follow the selected profile. Apply the [reference's clock boundaries](../../docs/references/GUINNESS-RULES.md#official-timing-boundary) with explicit estimated allowances.

## F5 — Persistence and comparison

**Depends on:** F3's stable scenario model; F4 for evaluated comparisons. Persistence work can proceed alongside F4.

- [ ] Save named local scenarios, duplicate them, and reload them without losing geometry or leg order.
- [ ] Support the proposed portable JSON import/export and CSV itinerary export.
- [ ] Detect incompatible/missing dataset or ruleset versions rather than silently substituting another snapshot.
- [ ] Compare two candidates by evaluated time, coverage, running distance, transfers, and fragile connections.

**Done when:** a saved complete rail rehearsal reloads with the same assumptions and data references, and a modified copy can be compared against the original with its differences explained.

## Later milestones

- **Silver Line:** integrate backend B4 and the reviewed required-stop inventory; retain separate rail-rehearsal and full-attempt coverage profiles.
- **Optimization:** generate candidates using the same evaluator and compare against a complete manual baseline; label results as best found, not proven optimal.
- **Attempt day:** offline next-leg instructions, observation/evidence events, and optional dated/stale-aware live context.

## Inputs and decisions still needed

| Input | When it matters |
|-------|-----------------|
| Local Google Maps/pedestrian-routing configuration | Before implementing provider-backed map and street routes in F2/F3. |
| Service date/start time with a covering dataset | Before evaluating a particular scenario in F4; editable per scenario. |
| Running/walking pace and access/transfer costs | For F3/F4 estimates; start with clearly labelled assumptions and calibrate through rehearsal. |
| Referenced official station-list image | Before validating full-record inventory; existing rail data can support a provisional rehearsal. |
| Separate evidence guide | Before implementing the later evidence/submission workflow. |

Check off each package only after its completion example works. Keep source rules in the reference and backend semantics in the backend plan instead of copying them into this work list.
