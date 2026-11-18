# hoi4-recorder

Recorders, shared game-reading helpers and the after-action report. Workspace-level notes (what every recording file is,
which tool makes it) are in `../CLAUDE.md`; per-tool detail is in `docs/tools.md`, memory offsets in `docs/game-layouts.md`, how to find a hidden game value in memory in
`docs/finding-things-in-memory.md` (read it before any memory scan).
Grep `hoi4rec/`, `tools/` and `docs/` before saying something isn't recorded.

## Layout
- `hoi4rec/` library: one `*rec.py` per recording, plus `memory` (RPM + RTTI), `pdx` (script parser), `gamefiles` (mod-aware
  lookup), `live`, `mapdata`, `templates`, `wars`, `units`, `clock`, `shared`, `drawing`. hoi4-custom-ai imports these, so keep
  their APIs stable and don't import from `hoi4ai` here (dependency runs one way: custom-ai -> recorder).
- `tools/` scripts: `cmdrec.py` runs the recorders; `report.py` builds `reports/NAME.html`; `rows.py`, `examples.py`,
  `campaignmap.py`, `map_now.py`, `state_snapshot.py`, `war_stats.py` and the other analysis scripts.
- `recordings/` ALL recorded games (git-ignored). `reports/`, `.cache/` (map cache) also git-ignored.
- `tools/_bridge.py` puts the hoi4-bridge client (`../hoi4-bridge/client` or `HOI4_BRIDGE_CLIENT`) and this repo on `sys.path`.

## Rules
- Read recordings with `python tools/rows.py DIR FILE col=value` (`--schema`, `--count COL`, `--final`); never grep a tag.
- The bridge stays generic; specialised recording/decoding lives here.
- Edit code with the Edit/Write tools, not inline Python/sed heredocs (backslashes get mangled).
- After changing report code, regenerate (`python tools/report.py recordings/NAME`) and grep the HTML for raw
  `lowercase_with_underscores` ids in text nodes. The user iterates by pointing at visual/localisation problems: fix,
  regenerate, commit, push.
- Timing tests: interleave modes in one session (HOI4 slows per reload).
- Commit straight to `main`, never branch. End commits with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
  (No git remote is set up yet; push once the user adds one.)
