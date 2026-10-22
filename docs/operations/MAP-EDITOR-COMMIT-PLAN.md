# Map editor implementation: commit plan

**Status:** approved for execution on 2026-10-22. The three source/documentation commits are made locally in the recorded order; resulting hashes are added in a separate `docs:` follow-up commit. Nothing is pushed by this task.

## Baseline and scope

At inspection, local `HEAD` was **`e6bbcef` — `docs: clarify project status and delivery plans`**, following the completed organization series recorded in [COMMIT-PLAN.md](COMMIT-PLAN.md). Recheck before acting: documentation and browser scenarios have been changing concurrently.

This series covers the initial **rail-rehearsal route studio**: pinned MBTA geometry, directed transfers, feasible timetable evaluation, connected ride/run/walk editing, Google Maps canvas integration, Google My Maps KML export, local scenario saving, and the associated tests/guides. It does not claim every B1–B3/F1–F5 item is complete.

Keep source archives, generated schedule/workbook/KML files, browser keys, Google billing/account details, and private scenarios/evidence out of Git. The implementation reuses the existing snapshot; no feed refresh or workbook regeneration belongs in these commits.

## Commit series

| Order | Commit message | Exact staging scope | Review focus / prerequisite |
|-------|----------------|---------------------|-----------------------------|
| 1 | `feat: add track-based rail itinerary evaluation` | `backend/rail_schedule/itinerary.py`, `backend/rail_schedule/test_itinerary.py` | Verify archive SHA-256 before combining sources; ordered shape clipping; real stop sequences and branch/platform permissions; directed/trip-specific transfers and pathways; published calendars and `24+` service hours; same-train continuity; downstream recalculation; coverage excludes foot-only and infeasible suffixes. Backend tests have no dependency on the new frontend. |
| 2 | `feat: add map route studio and My Maps export` | `frontend/map_editor/server.py`, `frontend/map_editor/static/index.html`, `frontend/map_editor/static/style.css`, `frontend/map_editor/static/app.js`, `frontend/map_editor/static/map.js`, `frontend/map_editor/test_server.py` | Depends on commit 1. Review connected editing/undo, fixed station anchors, explicit route alternatives, canonical server evaluation, source-aware foot geometry, snapshot/ruleset validation, local saves/import/export, KML coordinate order/namespace, Google canvas/key setup, and API/asset delivery. No credentials or downloaded vendor bundles. |
| 3 | `docs: document route studio setup and commit boundaries` | `README.md`, `frontend/map_editor/README.md`, `frontend/map_editor/USAGE.md`, `docs/README.md`, `docs/operations/COMMIT-PLAN.md`, `docs/operations/MAP-EDITOR-COMMIT-PLAN.md` | Running instructions, Google Cloud/referrer setup, manual KML import into the supplied My Maps project, API/scenario contract, verified versus pending behavior, component ownership, and remaining milestone criteria. Keep required Silver Line/full-record distinction and the existing organization history. |

These are separately reviewable commits in dependency order. Google provider configuration may be completed locally before or after the source series, but it is not a commit containing credentials. Publishing is a separate user instruction.

## Verification

### Before staging anything

```sh
git status --short
git diff
git log --oneline -10
git diff --check
git ls-files --others --exclude-standard
grep -rIlE 'AIza[0-9A-Za-z_-]{30,}' --exclude-dir=.git .
```

Untracked files do not appear in ordinary `git diff`; inspect their contents explicitly and review their full staged diff after selecting the exact paths. Investigate any files outside the scopes above before including them. A `grep` match must be investigated before staging; no browser key belongs in source, documentation, or scenarios.

### Commit 1: standalone backend checks

```sh
python3 -m unittest backend.rail_schedule.test_itinerary
python3 -m py_compile backend/rail_schedule/itinerary.py
```

### Commit 2: integrated checks

```sh
python3 -m unittest backend.rail_schedule.test_itinerary frontend.map_editor.test_server utilities.schedule_explorer.test_explore
node --check frontend/map_editor/static/app.js
node --check frontend/map_editor/static/map.js
python3 -m frontend.map_editor.server --help
python3 -m frontend.map_editor.server
```

Open **http://127.0.0.1:8001** and check:

- Create a direct ride and a multi-line path with real intermediate stations/platform changes.
- Add a foot link; edit waypoints/pace enough to change the following feasible train.
- Reorder into a disconnection, observe blocked timing/coverage, then undo.
- Save, duplicate, reload, and export JSON/CSV/KML; verify `24+` hours and source identity survive. Confirm the exported scenario JSON contains no key material.
- Inspect the narrow layout and browser console.
- With a real restricted browser key, load Google Maps, confirm station/rail alignment while panning/zooming, edit a foot polyline, and test a walking suggestion if Routes API is enabled.
- In the user's authenticated My Maps project, import an exported KML into a new layer and inspect the track-following geometry. Import is manual, not automatic synchronization.

The **Google canvas check is verified** with an operator-supplied restricted key held only in browser tab session storage (including reconnect after reload). Pedestrian suggestions (Routes API) and the private My Maps import remain account-dependent and unverified. They must not be described as passed simply because source code or the geographic preview works. Account setup is documented in the editor's Connect Google Maps dialog and [USAGE.md](../../frontend/map_editor/USAGE.md).

### Recorded results

- **17 tests passed:** 10 backend itinerary tests, 2 editor HTTP/KML tests, and 5 existing explorer checks. These ran against the retained local snapshot/archive, without skips.
- Both new JavaScript files passed `node --check`; server help/import checks passed.
- Browser checks verified the example's real rail geometry, transfer timing, 13 planned rail stations, foot-waypoint changes, save/duplicate, disconnected-edit handling, undo, and valid three-segment KML.
- A separate browser context verified the Google setup guide and 500-pixel layout without page overflow or browser console errors. Test scenarios did not replace the active user's browser scenario.
- A live Google Maps canvas was verified with an operator-supplied restricted browser key: Google tiles, MBTA track overlays, station-handle alignment and selection, and automatic reconnection after reload using the tab's session storage. The key was not written to scenarios, exports, logs, or the repository.
- Google `Routes API` pedestrian suggestions and import into the private My Maps project remain unverified until the corresponding Google project/account configuration is available.

Tests require generated exports and the matching archive. A missing-data skip is not validation. Do not regenerate or commit the snapshot merely to hide a failing check.

## Staging procedure after approval

For each row, stage only its exact files, review, then commit with the row's message. For example, commit 1:

```sh
git add -- backend/rail_schedule/itinerary.py backend/rail_schedule/test_itinerary.py
git diff --cached --name-status
git diff --cached --check
git diff --cached
```

Repeat the same staged review for commits 2 and 3 using their explicit file lists. Do not use `git add .`, sweep in concurrent changes, amend existing history, or push as part of an approval limited to local commits. After the series is committed, record the resulting hashes here in a separate `docs:` commit; do not amend the source commits. Leave provider-dependent verification honestly marked.
