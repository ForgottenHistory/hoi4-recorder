# hoi4-recorder

Records everything you and the AI do in Hearts of Iron IV
Split out of [hoi4-custom-ai](https://github.com/ForgottenHistory/hoi4-custom-ai); it reads the running game through
[hoi4-bridge](https://github.com/ForgottenHistory/hoi4-bridge) (singleplayer, Windows, Steam, tested on 1.19.4)

- `hoi4rec/` the library: one `*rec.py` recorder per kind of data (country, battles, politics, research, production,
  diplomacy, navy, air, intelligence, ...), plus the game-reading helpers they share (`memory`, `pdx`, `gamefiles`,
  `live`, `mapdata`, `templates`, `wars`, `units`, `clock`, `drawing`). hoi4-custom-ai imports these too.
- `tools/` command-line scripts: `cmdrec.py` runs the recorders; `report.py`, `rows.py`, `examples.py`, `campaignmap.py`,
  `apm.py`, `orbat.py`, ... read the recordings.
- `docs/tools.md` every script and what each recording contains; `docs/game-layouts.md` memory layouts (game 1.19.x).
- `recordings/` recorded games, `reports/` generated HTML, `.cache/` map cache (all git-ignored).

## Setup

Clone next to hoi4-bridge (or set `HOI4_BRIDGE_CLIENT` to its `client/` folder), then `pip install -r requirements.txt`.

    python tools/cmdrec.py <name>                 # record a playthrough into recordings/<name>
    python tools/report.py recordings/<name>      # -> reports/<name>.html

Reads game memory at offsets found by reverse engineering, so a game patch can break it. Unofficial; not affiliated
with Paradox Interactive. MIT, see [LICENSE](LICENSE).
