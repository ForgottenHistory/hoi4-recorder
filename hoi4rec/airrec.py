"""Air wings: each country's air wings, where they are based and the mission they fly.

AirLog(path, names, tags, others).step(date, lines) writes air_regions.tsv (see _regions), air_stock.tsv (see _stock:
daily, per design: planes in wings, in the stockpile, production rate) and, to air.tsv:
  date  change  country  wing  name  base  state  equipment  planes  mission  region  period  experience  was
wing the wing's id (handle 69), base the air base it sits at (handle 65 id) and state that base's state, equipment
the plane design (handle 70 id), planes how many it has, mission none / air_superiority / cas / interception /
strategic_bombing / naval_strike / nuke / paradrop / kamikaze / port_strike / attack_logistics / air_supply /
training / mines_planting / mines_sweeping / recon / naval_patrol, region the strategic region of the mission (kept by
the game after the mission ends), period day / night / day_and_night, experience 0-1 (written, not compared; planes
too, as losses and reinforcement change it). change: start (the first read of a country), new (deployed, or split
off another wing), changed, removed (disbanded, merged into another wing, or destroyed). was: what changed, as
field=old (e.g. "mission=none;region=38", "base=9").

Reads at the first call and each new in-game day: TAGS (the recorded countries) each time, OTHERS() (a callable, e.g.
MioLog's producing countries) every FULL_DAYS days, and TAGS at once after an air command in the record LINES on one
of their wings or on no known wing (e.g. a deployment). A read covers the wings these countries held at the last
read and the ids past the highest seen (a new wing), every wing in the game (~1.5 s for 250) at the first call and
every FULL_DAYS days.

Read with bridge.write 69 ID (the wing as the game saves it: count, experience, mission={ type period active
strategic_region }, tag, equipment, name) for every wing id from 1 to past the highest seen; the base from memory:
the wing (bridge.object 69 ID gives it +0x10) holds its CAirWingPool at +0x28, the pool its air base handle 65:ID at
+0x18; bridge.write 65 ID gives the base's state. mission type is a bit of the mission mask (allow_mission_type is
the mask of the missions a wing can fly), 0 none: 1 air superiority, 2 cas, 4 interception, 8 strategic bombing,
2048 training seen (bits 0-3, 11); the others follow the game's order (fighters may fly bits 0, 2 and 11, tactical
bombers 1, 3, 8, 9 and 11). period 0 day, 1 night, 2 day and night.

The player's commands (in command_record.tsv; the owner column is empty, the AI uses the same ones). Lists of wings
are written by install_rules() (L+0x28=[69:1,69:3]):
  CStratAirSetMissionCommand     wings list +0x28 (count +0x30), mission mask +0x40, on byte +0x44 (0: mission off)
  CStratAirEnableMissionCommand  wings list +0x28
  CStratAirDayNightCommand       wing 69:ID +0x28, period +0x30
  CStratAirTransferCommand       wing 69:ID +0x28, air base 65:ID +0x30
  CStratAirSplitCommand          wing 69:ID +0x28, planes +0x30
  CStratAirConsolidateCommand    wings list +0x28 (merged into the first)
  CDeleteAirWingCommand          wings list +0x28 (disbanding)
  CDeployAirWingCommand          air base 65:ID +0x30 (a new wing from the stockpile)
"""
import os
import re

from hoi4rec import shared
from hoi4bridge import country_block, send

FULL_DAYS = 7
WING, BASE = 69, 65
STOCK_HEADER = "date\tcountry\tdesign\twings\tstock\trate\tfactories\tlost"
REGION_HEADER ="date\tcountry\tregion\tmission\twings\tplanes\teffective\tair_superiority\tlost"
HEADER = ("date\tchange\tcountry\twing\tname\tbase\tstate\tequipment\tplanes\tmission\tregion\tperiod\texperience"
          "\twas")
FIELDS = ("name", "base", "state", "equipment", "planes", "mission", "region", "period", "experience")
COMPARE = ("name", "base", "state", "equipment", "mission", "region", "period")
LISTED = ("CStratAirSetMissionCommand", "CStratAirEnableMissionCommand", "CStratAirConsolidateCommand",
          "CDeleteAirWingCommand")
SINGLE = ("CStratAirDayNightCommand", "CStratAirTransferCommand", "CStratAirSplitCommand")
COMMANDS = LISTED + SINGLE + ("CDeployAirWingCommand",)
MISSIONS = ("air_superiority", "cas", "interception", "strategic_bombing", "naval_strike", "nuke", "paradrop",
            "kamikaze", "port_strike", "attack_logistics", "air_supply", "training", "mines_planting",
            "mines_sweeping", "recon", "naval_patrol")
PERIODS = ("day", "night", "day_and_night")
_LIST = re.compile(r"L\+0x28=\[([^\]]*)\]")


def install_rules():
    """Have bridge.cmdrec write the wings the listed air commands name."""
    return all(send(f"bridge.cmdrec list {c} 0x28 0x30 8")[0].startswith("OK") for c in LISTED)


def mission(mask):
    mask = int(mask)
    if not mask:
        return "none"
    names = [MISSIONS[b] if b < len(MISSIONS) else f"bit{b}" for b in range(mask.bit_length()) if mask >> b & 1]
    return "+".join(names)


def parse(line):
    """A record line -> (class, [wing ids]) of an air command, or None."""
    p = line.rstrip("\n").split("\t")
    if len(p) < 8 or p[2] not in COMMANDS:
        return None
    if p[2] in LISTED:
        m = _LIST.search(p[8] if len(p) > 8 else "")
        return p[2], [int(h.split(":")[1]) for h in m.group(1).split(",") if h.startswith("69:")] if m else []
    b = bytes.fromhex(p[7])
    if p[2] in SINGLE and len(b) >= 0x30 and int.from_bytes(b[0x28:0x2c], "little") == WING:
        return p[2], [int.from_bytes(b[0x2c:0x30], "little")]
    return p[2], []


def _segments(lines):
    """The replies of a batch of bridge.write calls, one text per call."""
    out, cur = [], None
    for ln in lines:
        if ln.startswith(("OK ", "FAIL", "ERROR")):
            if cur is not None:
                out.append("\n".join(cur))
            cur = [ln]
        elif cur is not None:
            cur.append(ln)
    if cur is not None:
        out.append("\n".join(cur))
    return out


def _get(text, key):
    m = re.search(r"\n\t*" + key + r"=(\"[^\"]*\"|[^\s{}]*)", text)
    return m.group(1).strip('"') if m else ""


class AirLog:
    def __init__(self, path, names=None, tags=(), others=lambda: ()):
        from hoi4rec.eventrec import Names
        from hoi4rec.memory import Process
        self.proc = Process()
        self.names = names or Names()
        self.tags = [t for t in tags if t and t != "none"]
        self.others = others
        self.top = 0                # the highest wing id seen
        self.owner = {}             # wing id -> tag
        self.held = {}              # tag -> {wing id: {field: value}}
        self.state = {}             # air base id -> state id
        self.started = False
        self.day, self.days = None, 0
        new = not os.path.exists(path)
        self.f = open(path, "a", encoding="utf-8")
        if new:
            self.f.write(HEADER + "\n")
        rpath = os.path.join(os.path.dirname(path), "air_regions.tsv")
        new = not os.path.exists(rpath)
        self.fr = open(rpath, "a", encoding="utf-8")
        if new:
            self.fr.write(REGION_HEADER + "\n")
        self.regions = {}           # tag -> {(region, mission): (wings, planes, effective, air_superiority)}
        self.base = {}              # (tag, design) -> [planes at the first read, production since, last rate]
        spath = os.path.join(os.path.dirname(path), "air_stock.tsv")
        new = not os.path.exists(spath)
        self.fs = open(spath, "a", encoding="utf-8")
        if new:
            self.fs.write(STOCK_HEADER + "\n")

    def _bases(self, ids):
        """{wing id: air base id} of wings IDS."""
        out = {}
        for wid, r in zip(ids, send(*[f"bridge.object {WING} {i}" for i in ids]) if ids else ()):
            m = re.search(r"@0x([0-9a-fA-F]+)", r) if r.startswith("OK") else None
            pool = self.proc.u64(int(m.group(1), 16) + 0x28) if m else 0
            out[wid] = str(self.proc.i32(pool + 0x1c)) if pool and self.proc.i32(pool + 0x18) == BASE else ""
        return out

    def _state(self, base):
        if base and base not in self.state:
            self.state[base] = _get("\n" + "\n".join(send(f"bridge.write {BASE} {base}")), "state")
        return self.state.get(base, "")

    def wings(self, ids=None):
        """{tag: {wing id: {field: value}}} of wings IDS and those past the highest id seen; of every wing in the
        game if IDS is None."""
        out, wid, last = {}, 1, 0
        if ids is not None:
            ids = list(ids)
            for i in set(ids) - set(self._wings(ids, out)):
                self.owner.pop(i, None)
            wid = self.top + 1
            while self._wings(range(wid, wid + 32), out):
                wid += 32
        while ids is None and wid <= max(self.top, last) + 64:
            last = max([last] + self._wings(range(wid, wid + 256), out))
            wid += 256
        self.top = max([self.top] + [i for ws in out.values() for i in ws])
        return out

    def _wings(self, ids, out):
        """Reads wings IDS into OUT ({tag: {wing id: fields}}); returns the ids found."""
        found, ids = [], list(ids)
        for k in range(0, len(ids), 256):
            for text in _segments(send(*[f"bridge.write {WING} {i}" for i in ids[k:k + 256]])):
                if not text.startswith("OK"):
                    continue
                i = re.search(r"id=\{ id=(\d+) type=69 \}", text)
                tag = _get(text, "tag")
                if not i or not tag:
                    continue
                i = int(i.group(1))
                found.append(i)
                eq = re.search(r"equipment=\{\s*equipment=\{\s*id=\{ id=(\d+)", text)
                mis = text[text.find("mission={"):] if "mission={" in text else ""
                per = _get(mis, "period")
                out.setdefault(tag, {})[i] = {
                    "name": _get(text, "name"), "base": "", "state": "", "equipment": eq.group(1) if eq else "",
                    "planes": _get(text, "count"), "mission": mission(_get(mis, "type") or 0),
                    "region": _get(mis, "strategic_region"),
                    "period": PERIODS[int(per)] if per.isdigit() and int(per) < len(PERIODS) else per,
                    "experience": _get(text, "experience"),
                    "active": _get(mis, "active"), "executing": _get(mis, "executing_mission"),
                    "effective": _get(mis, "effective_planes_count"),
                    "air_superiority": _get(mis, "effective_air_superiority")}
        return found

    def _regions(self, date, tag, now, last):
        """Writes the rows of air_regions.tsv for TAG: per strategic region and mission the wings, planes, effective
        planes and air superiority of its wings that are on a mission, with `lost` = the planes the wings that were
        there at the last read have lost since (only drops; reinforcement hides some). A row is written when
        anything but the plane count of a group changed, or planes were lost."""
        lost = {}
        for i, v in now.items():
            o = (last or {}).get(i)
            if o and o["planes"].isdigit() and v["planes"].isdigit() and int(o["planes"]) > int(v["planes"]):
                k = (o["region"], o["executing"] if o["active"] == "yes" else "none")
                lost[k] = lost.get(k, 0) + int(o["planes"]) - int(v["planes"])
        groups = {}
        for v in now.values():
            if not v["region"]:
                continue
            k = (v["region"], v["executing"] if v["active"] == "yes" else "none")
            g = groups.setdefault(k, [0, 0, 0, 0.0])
            g[0] += 1
            g[1] += int(v["planes"] or 0)
            g[2] += int(v["effective"] or 0)
            g[3] = round(g[3] + float(v["air_superiority"] or 0), 1)
        old = self.regions.get(tag, {})
        n = 0
        for k in sorted(set(groups) | set(old) | set(lost)):
            g = tuple(groups.get(k, (0, 0, 0, 0)))
            if g != old.get(k) or lost.get(k):
                self.fr.write("\t".join((date, tag, k[0], k[1]) + tuple(map(str, g)) + (str(lost.get(k, 0)),)) + "\n")
                n += 1
        self.regions[tag] = {k: tuple(g) for k, g in groups.items()}
        return n

    def _stock(self, date, tag, now):
        """Writes air_stock.tsv rows for TAG: per aircraft design the planes in wings, in the stockpile, and the
        production rate (sum over its lines of speed / cost, units per day on the game's own scale) with the
        factories on it. Only designs a wing uses or the stockpile holds. Reinforcement moves planes from the
        stockpile into wings, so wings + stock falls only by losses (and rises by production). `lost` = planes lost
        since this recorder's first read of the design = production since (rate per day read) - (change in wings +
        stock). Checked live: British fighters 32 against the panel's 32 over 3 days; German 9 against 13 (reading
        times differ). Planes sold, lent or scrapped would count as lost too."""
        text = country_block(tag)
        stock = {}
        m = re.search(r"\n\t*equipments=\{((?:\s*equipment=\{\s*id=\{ id=\d+ type=70 \}\s*amount=\d+\s*\})+)", text)
        for i, a in re.findall(r"id=(\d+) type=70 \}\s*amount=(\d+)", m.group(1) if m else ""):
            stock[i] = int(a)
        rate, fact = {}, {}
        for sp, cost, i in re.findall(
                r"speed=([\d.]+)\s*cost=([\d.]+)\s*requested_factories=\d+\s*equipment_variant_index=\{ id=(\d+) type=70 \}",
                text):
            rate[i] = rate.get(i, 0.0) + (float(sp) / float(cost) if float(cost) else 0.0)
        for fa, i in re.findall(r"active_factories=(\d+)[^{}]*?equipment_variant_index=\{ id=(\d+) type=70 \}", text):
            fact[i] = fact.get(i, 0) + int(fa)
        wings = {}
        for v in now.values():
            if v["equipment"]:
                wings[v["equipment"]] = wings.get(v["equipment"], 0) + int(v["planes"] or 0)
        for i in sorted(set(wings) | set(stock), key=int):
            total = wings.get(i, 0) + stock.get(i, 0)
            base, made, last = self.base.setdefault((tag, i), [total, -rate.get(i, 0.0), rate.get(i, 0.0)])
            made += last                    # a day of production at the rate of the last read
            self.base[(tag, i)] = [base, made, rate.get(i, 0.0)]
            lost = round(made - (total - base), 1)
            self.fs.write("\t".join((date, tag, i, str(wings.get(i, 0)), str(stock.get(i, 0)),
                                     f"{rate.get(i, 0.0):.3f}", str(fact.get(i, 0)), str(lost))) + "\n")

    def step(self, date, lines=()):
        """DATE as for ProductionLog.step. Returns the rows written."""
        day = date.split(",", 1)[1] if "," in date else date.split(" ", 1)[0]
        todo = []
        for cls, ids in filter(None, map(parse, lines)):
            known = [self.owner[i] for i in ids if i in self.owner]
            todo += [t for t in known if t in self.tags] if known else self.tags   # others: the weekly read
        new_day = day != self.day
        if new_day:
            self.days += 1
            todo += self.tags
            todo += list(self.others() or ()) if not self.started else shared.part(self.others(), self.days, FULL_DAYS)
        self.day = day
        rows = []
        todo = list(dict.fromkeys(todo))
        if todo:
            full = not self.started or (new_day and self.days % FULL_DAYS == 2)
            every = self.wings(None if full else [i for i, t in self.owner.items() if t in todo])
            for tag, ws in every.items():
                for i in ws:
                    self.owner[i] = tag
            for tag in todo:
                now, last = every.get(tag, {}), self.held.get(tag)
                bases = self._bases(sorted(now))
                for i, v in now.items():
                    v["base"] = bases.get(i, "")
                    v["state"] = self._state(v["base"])
                for i, v in sorted(now.items()):
                    old = None if last is None else last.get(i)
                    if old is None:
                        rows.append(("start" if last is None else "new", tag, str(i)) + tuple(v[f] for f in FIELDS)
                                    + ("",))
                    elif any(old[f] != v[f] for f in COMPARE):
                        was = ";".join(f"{f}={old[f]}" for f in COMPARE if old[f] != v[f])
                        rows.append(("changed", tag, str(i)) + tuple(v[f] for f in FIELDS) + (was,))
                for i, v in sorted((last or {}).items()):
                    if i not in now:
                        rows.append(("removed", tag, str(i)) + tuple(v[f] for f in FIELDS) + ("",))
                if last is not None or not self.started:
                    self._regions(date, tag, now, last)
                if new_day and tag in self.tags:
                    self._stock(date, tag, now)
                self.held[tag] = now
        self.started = True
        for row in rows:
            self.f.write("\t".join((date,) + row) + "\n")
        self.f.flush()
        self.fr.flush()
        self.fs.flush()
        return len(rows)

    def close(self):
        self.f.close()
        self.fr.close()
        self.fs.close()
