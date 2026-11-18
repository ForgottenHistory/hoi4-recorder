"""The air-zone panel's loss counters (Days / Months / Years views), read live from game memory.

Layout (found 2026-11-18, checked against the panel and the save's strategic_air/TAG/history blocks):
  holder   an object with vtable HOLDER_VTABLE (RTTI says CStrategicAir; per country, the primary-vtable CStrategicAir
           is another object): country id +0x88, region count +0x140, pointer to an array indexed by strategic region id
           +0x150. Entries are 0 or a CLoopHistory.
  CLoopHistory (vtable HISTORY_VTABLE): the containers at +0x10 (Days, 30 slots), +0x18 (Months, 12), +0x20 (Years).
  CLoopHistoryContainer: +0x08 pointer to an array of SLOTS element pointers, +0x10 dword slots, +0x24 dword = the ring
           offset (the next slot to write; the newest day is offset-1).
  element  +0x00 pointer to COLUMNS int64 values, +0x08 dword count (89 for air). Fixed point, 100000 = 1.0.
Columns (7 per channel, in the order total, air battle, AA, accident): fighters 3-6, tactical bombers 10-13, CAS 17-20,
39 = bombers disrupted, 44/45 = enemy fighters lost; see tools/air_losses.py.

    read(proc) -> {(country id, region): {"days": (offset, rows), "months": ..., "years": ...}} with rows[slot][column]
"""
import struct

COLUMNS = 89
SCALE = 100000.0
ENEMY = 41      # the enemy block mirrors ours at +41 (GER c41 = ENG c0, GER c80 = ENG c39)


def _names():
    """Column -> name. Ours: 0-2 buildings / troops / ships bombed, then 7 columns per loss channel (total, air battle,
    shot down by AA, accident; the rest unseen): fighters 3, bombers 10, CAS 17; 39 bombers disrupted. The enemy
    block (+41) is what WE did to them: buildings / troops bombed, ships sunk, fighters 44, bombers 51, CAS 58 lost
    (total, air battle, AA: no accidents), 80 their bombers disrupted. Seen only for non-zero values; the unseen
    channels (transports, trains, trucks, railway guns, missiles) are in the gaps and are not named."""
    out = {0: "buildings_bombed", 1: "troops_bombed", 2: "ships_bombed", 39: "bombers_disrupted"}
    for base, ch in ((3, "fighters"), (10, "bombers"), (17, "cas")):
        for k, r in enumerate(("total", "air_battle", "aa", "accident")):
            out[base + k] = f"{ch}_lost_{r}"
    for c in list(out):
        out[c + ENEMY] = "enemy_" + out[c]
    return out


NAMES = _names()
VIEWS = (("days", 0x10), ("months", 0x18), ("years", 0x20))


def holders(proc, cache={}):
    """Addresses of the per-country holders. They persist for the whole game, so the scan runs once per session."""
    key = proc.pid if hasattr(proc, "pid") else id(proc)
    if key not in cache:
        hv = _find_holder_vtable(proc)
        cache[key] = [] if hv is None else list(proc.search(struct.pack("<Q", hv), align=8))
    return cache[key]


def _find_holder_vtable(proc):
    """The secondary CStrategicAir vtable: any vtable whose RTTI complete-object locator names CStrategicAir but whose
    offset is not 0. Found as the vtable that sits at +0 of an object holding the region-history array pointer."""
    primary = proc.vtable_of("CStrategicAir")
    img = proc.read(proc.base, proc.size)
    if not img or primary is None:
        return None
    # the secondary vtable's COL points at the same type descriptor as the primary's; scan COLs for that
    pcol = proc.u64(primary - 8)
    td = struct.unpack_from("<i", proc.read(pcol, 0x18), 12)[0]
    out, pos = [], 0
    pat = struct.pack("<i", td)
    while True:
        j = img.find(pat, pos)
        if j < 0:
            break
        pos = j + 1
        col = j - 12
        if col < 0:
            continue
        sig, off = struct.unpack_from("<ii", img, col)
        if sig != 1 or off == 0:
            continue
        k = img.find(struct.pack("<Q", proc.base + col))
        if k >= 0 and k % 8 == 0:
            out.append(proc.base + k + 8)
    return out[0] if out else None


def _container(proc, addr, history_vt):
    """(offset, rows) of the CLoopHistoryContainer at ADDR, or None."""
    d = proc.read(addr, 0x28)
    if not d:
        return None
    arr, size, ring = struct.unpack_from("<QI", d, 8)[0], struct.unpack_from("<I", d, 0x10)[0], \
        struct.unpack_from("<I", d, 0x24)[0]
    if not arr or not 0 < size <= 64:
        return None
    b = proc.read(arr, size * 8)
    if not b:
        return None
    rows = []
    for p in struct.unpack("<%dQ" % size, b):
        e = proc.read(p, 12) if p else None
        buf = proc.read(struct.unpack_from("<Q", e, 0)[0], COLUMNS * 8) if e and struct.unpack_from("<i", e, 8)[0] == COLUMNS else None
        rows.append([v / SCALE for v in struct.unpack("<%dq" % COLUMNS, buf)] if buf else [0.0] * COLUMNS)
    return ring, rows


def read(proc):
    """{(country id, region id): {view: (offset, rows)}} of every region history of every country."""
    hvt = proc.vtable_of("CLoopHistory")
    out = {}
    for h in holders(proc):
        n, arr = proc.i32(h + 0x140), proc.u64(h + 0x150)
        if not arr or not 0 < n < 2000:
            continue
        b = proc.read(arr, n * 8)
        if not b:
            continue
        for region, p in enumerate(struct.unpack("<%dQ" % n, b)):
            if p < 0x10000 or proc.u64(p) != hvt:
                continue
            views = {}
            for name, off in VIEWS:
                c = _container(proc, proc.u64(p + off), hvt)
                if c and len(c[1]) and any(any(r) for r in c[1]):
                    views[name] = c
            if views:
                out[(proc.i32(h + 0x88), region)] = views
    return out
