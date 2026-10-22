# Commit proposal: archive initial assistant work

> Superseded historical proposal. The current repository-wide commit sequence is `docs/operations/COMMIT-PLAN.md`.

**Status:** proposal only. No files have been staged, committed, or pushed by this archival task.

## Repository check

- GitHub: <https://github.com/thejackluo/t> (`origin`).
- GitHub reports a **public, empty** repository with no branch heads.
- The local branch is `main`, with **no commits yet**. The working files are untracked.
- Consequently, the first commit would add the archived files at their final locations; Git has no earlier committed files to record as renames.

## Recommended commit

**Message:** `docs: archive initial planning and setup work`

Use one focused first commit. The archive, retired installer source, and short replacement entry points belong together so a reader immediately understands their status.

### Exact staging scope

1. `docs/archive/initial-assistant-work/` — historical design/research/plans, former README/guidance/setup documents, GSD config/runtime pin, and the retired installer saved as text.
2. `README.md` — small current front page linking the archive and proposal.
3. `docs/README.md` — explanation of each document.
4. `docs/COMMIT-PROPOSAL.md` — this proposal.
5. `AGENTS.md` — concise current guidance stating that archived plans are reference material.
6. `.gitignore` — excludes installed tooling, credentials, feeds, generated output, and Python caches/environments.

### Outside this commit

- `build_schedule.py`, `schedule_lookup.py`, `validate_schedule.py`, and `requirements.txt`.
- `output/`, `data/`, and `docs/RAIL-SCHEDULE-API-PLAN.md`.
- The separately saved discussion/session files under `docs/planning/` and the `.planning` shortcut.
- Later product/rules discussion documents: `docs/MAP-EDITOR-REQUIREMENTS.md` and `docs/GUINNESS-RULES.md`; independently added `explore.py` and `explorer/` work.
- Generated `.opencode/`, local environments/caches, and credentials.

The scheduling work can receive its own review and commit later. This proposal does not evaluate or regenerate it.

## Proposed review sequence

These commands are a plan for a later approved commit, not commands executed by this task:

```sh
git status --short
git add -- .gitignore AGENTS.md README.md docs/README.md docs/COMMIT-PROPOSAL.md docs/archive/initial-assistant-work
git diff --cached --name-status
git diff --cached --check
git diff --cached
```

Review the staged list against the six entries above. In particular, avoid `git add .`, which would include the untracked scheduling tools and discussion material.

After reviewing the staged content, the proposed commit command is:

```sh
git commit -m "docs: archive initial planning and setup work"
```

Publishing to GitHub is a subsequent step, after the local commit is requested and reviewed. No push is part of this proposal's execution.

## Verification for this change

- Retired installer is no longer at the active `scripts/install-gsd.mjs` path and is preserved verbatim as `.mjs.txt`.
- Archived planning documents clearly identify themselves as historical.
- Current front pages link to the archive and explain each document.
- Silver Line remains recorded as a future capability.
- Git object hashes confirm no content changes to the three scheduling scripts, dependency file, scheduling guide, output workbook/manifest/validation report, and saved `state.json`. The discussion checkpoint changed during concurrent work; this archival task did not edit it. No schedule rebuild is needed for a documentation archive.

## What this proposal does not claim

The archived documents describe ideas and acceptance criteria; they are not evidence that the interactive map or optimizer has been implemented. The initial Guinness category research is a dated observation, not a fresh rules confirmation.
