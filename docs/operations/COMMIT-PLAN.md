# Git operations: organization history and future changes

## Completed organization commits

The approved five-commit repository reorganization is **complete locally**. This is an operations record, not a pending product build plan. Product work is broken down in the [backend plan](../../backend/rail_schedule/PLAN.md#delivery-plan) and [frontend plan](../../frontend/map_editor/PLAN.md).

| Order | Commit | Message | Boundary |
|-------|--------|---------|----------|
| 1 | `ec72db5` | `docs: define repository structure and rule references` | Root guides, design overview, ignore rules, operations, and the Guinness reference move. |
| 2 | `dde5624` | `refactor: group rail schedule backend tools` | Backend Python tools, dependency file, path handling, and documentation. |
| 3 | `7abe98d` | `refactor: isolate schedule explorer utility` | Explorer server, static assets, integration checks, and guide. |
| 4 | `9058ea5` | `docs: define map editor frontend project` | Frontend overview and captured requirements. |
| 5 | `fc1d1b3` | `docs: preserve initial planning and session archive` | Historical plans, retired installer, and old session metadata. |

The baseline was `5f14f0b` (`docs: add Guinness World Record guidelines`), which tracked only the original `docs/GUINNESS-RULES.md`. The organization series recorded its move to `docs/references/GUINNESS-RULES.md` with identical content. Other previously untracked files entered history at their organized locations.

The series was not pushed by that task. Remote: <https://github.com/thejackluo/t> (`origin`). Check current local/remote state before publishing or starting another commit series; the original empty-remote observation is historical.

## Boundaries for future commits

The current map-editor implementation was committed as a separate **[three-commit series](MAP-EDITOR-COMMIT-PLAN.md)** covering backend routing/evaluation, the route studio/Google integration, and setup documentation. The linked document records the exact scopes, verification, and resulting hashes; publishing remains a separate user instruction.

| Change | Primary scope | Review/check |
|--------|---------------|--------------|
| Documentation/planning | Root/project guides and the specific plans changed | Correct status, links, dependencies, and separation of confirmed choices from proposals. |
| Backend contract/graph/evaluator | `backend/rail_schedule/` | Calendar/overnight/platform/boarding semantics and the work package's completion example. |
| Explorer compatibility/UI | `utilities/schedule_explorer/` | Data-integrity checks, static/API smoke check, and JavaScript syntax as applicable. |
| Map editor implementation | `frontend/map_editor/` | The F1–F5 completion examples, including downstream recalculation and save/reload when relevant. |
| Rule-reference update | `docs/references/` | Preserve source provenance; reconcile affected product plans in the same change or a clearly linked follow-up. |

An integration change may need both backend and frontend files. Keep dependent contract changes together or in a documented compatible sequence; folder boundaries should not create knowingly broken intermediate behavior.

Only commit, push, or create a PR when explicitly requested. Approval of the completed organization sequence is not automatic approval for future edits.

## Review procedure

```sh
git status --short
git log --oneline -10
git diff
git diff --check
```

When a commit is requested, stage the reviewed files explicitly, then inspect:

```sh
git diff --cached --name-status
git diff --cached --check
git diff --cached
```

Avoid `git add .` when unrelated work is present. Before a requested push, inspect `git remote -v` and remote heads/tracking. Keep `.opencode/`, environments/caches, downloaded feeds, `output/`, credentials, and private attempt evidence out of Git. Retired `.planning` state and archived instructions are not active staging/build instructions.

## Existing verification commands

Run from the repository root, using an interpreter with the backend dependencies installed where required:

```sh
python3 -m unittest utilities.schedule_explorer.test_explore
node --check utilities/schedule_explorer/static/app.js
python3 -m backend.rail_schedule.build_schedule --help
python3 -m backend.rail_schedule.validate_schedule --help
```

Explorer integration checks require generated exports and otherwise explicitly skip. The existing expected dates/values target the recorded October–December 2026 snapshot; review them when adopting a newer feed. Documentation-only changes need documentation/link/whitespace review rather than a schedule rebuild.

## Verification recorded for the organization series

- Five explorer checks passed, including HTML/JavaScript/CSS delivery and metadata; they also passed from an unrelated working directory.
- JavaScript syntax and backend module/direct-script help checks passed.
- The sample lookup returned the 08:08 Ashmont departure and eight-minute scheduled wait.
- Workbook, manifest, and validation-report hashes were unchanged; the Guinness reference matched its committed source exactly.

These are dated results from the reorganization, not a claim that new product milestones or future snapshots have been validated.
