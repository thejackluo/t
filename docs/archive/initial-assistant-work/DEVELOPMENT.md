# Development setup

> Archived setup instructions. The installer is retired and preserved as text at `scripts/install-gsd.mjs.txt`; commands below describe the former layout and should not be run as current setup instructions.

## GSD / Get Shit Done

The original [Get Shit Done repository](https://github.com/gsd-build/get-shit-done) is archived and points to [GSD Core](https://github.com/open-gsd/gsd-core). This project uses GSD Core 1.18.0, installed locally for OpenCode.

To reproduce the generated `.opencode/` installation, run from the repository root:

```sh
node scripts/install-gsd.mjs
```

The bootstrap requires Node.js 22 or later, npm/npx, and network access. It runs GSD with pinned Node.js 24.22.1 and pins the MCP server to the same GSD release. The upstream installer also manages runtime preferences in `~/.gsd/defaults.json`.

Quit and restart OpenCode after installing or changing its configuration. Then use `/gsd-help`, `/gsd-progress`, or `/gsd-discuss-phase 1`. The installed GSD release supports the current OpenCode 1.x adapter; upstream says 1.x support ends December 31, 2026.

## Documentation layout

All written material is under `docs/`. GSD's planning files live in `docs/planning/`; the root `.planning` entry is a relative symlink to that directory. Edit either path and you edit the same file. Keep the symlink intact for GSD commands.

The symlink is part of the repository layout; a checkout must preserve symbolic links. It can be recreated on this Linux workspace with `ln -s docs/planning .planning` if the shortcut is missing.

## Python scheduling tools

The separate workbook guide remains at `docs/RAIL-SCHEDULE-API-PLAN.md` in the repository. Scheduling work is outside this archive.
