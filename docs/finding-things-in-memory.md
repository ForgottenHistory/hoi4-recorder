# Finding a game value in memory: patterns and method

Worked example: the air-zone panel's loss counters (Days / Months / Years), 2026-11-18. It took far too long because
value scans were the wrong tool. Next time follow this order.

## 1. Ask where the game already stores it in plain text
- **The plaintext save is the fastest map.** Save (autosave works), then grep for a value the UI shows. The panel
  numbers were in `strategic_air/TAG/history/REGION/history_queue/N/data` (30 days x 89 columns). That gave the
  structure, the sizes (30 / 12 / 1-5 slots, 89 columns) and exact expected values for every column.
- **If a UI number survives a save reload, it is saved state, so it is in the save and in memory.** (The user's
  hint: "I reloaded and still see the same numbers".)
- `tools/air_losses.py` shows the pattern: a small parser over the save, verified against what the panel shows.
- Save keys that end in `_queue`, `history`, `max_elements`, `offset`, `is_full`: a ring buffer (`CLoopHistory*`).

## 2. Map columns with known numbers, not guesses
Have the user set up a situation with distinct, easy numbers (e.g. 4 fighters air battle, 1 accident, 16 bombers by
AA, 2 accident) and read the panel. Match the save's columns to them. Distinct values per channel identify the layout
(here 7 columns per channel: total, air battle, AA, accident). Save a little later than the readings and the numbers
will have grown: match the *relations* (total = sum of parts), not only the digits.

## 3. In memory, search by structure, not by value
Value scans (numpy windows, strides, pointer following) gave dozens of false positives and cost hours. They failed
because the real storage was not what was assumed.
- **int64 fixed point**: the game stores fractions as integer x 100000 (`200000` = 2.0). The save prints `3`, memory
  holds `300000` in 8 bytes. A search for int32/float32 `3` never matches. Look for the scale (a 2.0 became 200000,
  followed by zero words, which also told us the element was 8 bytes: the first dump read as int32 had every real
  column at an even index).
- **Rings of pointers**: 30 slots are not 30 values. `CLoopHistoryContainer` holds a pointer to 30 element pointers;
  each element is a small vector `{pointer to buffer, dword count}`. So the series is not contiguous in memory.
- Dump a candidate with both views (`<Nq` and `<2Ni`) and decide the width from where the nonzero words sit.

## 4. Use RTTI class names to find the object
`Process.vtable_of(name)` / `find_objects(name)` / `class_of(addr)` (hoi4rec/memory.py). Steps that worked:
1. List class names in the image matching a keyword (`re.findall(rb"\.\?AV([A-Za-z0-9_@]*History[A-Za-z0-9_@]*)@@", image)`).
   `Histor`, `Statistic`, `Ring`, `Loop` found `CLoopHistory`, `CLoopHistoryContainer`, `CLoopHistoryContainerQueue`.
2. `find_objects` on the likeliest class; dump 0x70 bytes as qwords and read the shape: a vtable, pointers, a dword
   pair `0x1e0000001e` (size 30, capacity 30), `0x...0b` high dword = the ring offset (matched the save's
   `offset=`). A pair of equal dwords is a vector's size/capacity; `{ptr, 0x5900000059}` is an 89-element vector.
3. Filter all instances by a property you know from the save (slot count 30 and element size 89: 20 of 26,429
   containers), decode them, and compare column sums with the panel. A match proves the decoding.

## 5. Walk up to the owner by searching for pointers to the object
`proc.search(struct.pack("<Q", addr), align=8)` finds every reference. Dump the words around the hit and call
`class_of` walking back in 8-byte steps until a class name appears. Here: container -> `CLoopHistory` ->
region-indexed sparse array (regions 1 and 7 were 6 slots apart) -> the owner at +0x150 with count at +0x140.
- **The class name can lie about the object.** The owner's RTTI said `CStrategicAir` but it was not the
  primary-vtable `CStrategicAir` objects (573 of them, no history). It had a *secondary* vtable of the same class
  (a COL with nonzero offset). `find_objects(name)` only finds the primary one. `airlosses._find_holder_vtable`
  finds the secondary.
- Tag from the owner: look for the country id (here +0x88, GER=1, ENG=2). `Names.tag(cid)` resolves it. Check the
  ids against two countries you know (their region lists matched the save: GER 1, 7, 38; ENG 1, 7).
- Don't hard-code a vtable address: ASLR moves the image. Derive it from RTTI each session.

## 6. Verify against three things before trusting it
the panel (live numbers), the save (same structure and values), and a second country / second region (guards against
a coincidence). Then record it with a test through the real recorder class and time it (first read 9 s because of the
one-off scan, then 0.1 s).

## Checklist for the next hidden counter
1. Save, grep the save for the UI value. 2. Get distinct numbers from the user and map the columns. 3. RTTI keyword
search for the container class. 4. Dump one instance as qwords AND int32; look for the size/capacity pair and the
x100000 scale. 5. Filter instances by shape, decode, compare sums with the panel. 6. Search pointers back to the
owner; check for secondary vtables; find the country id. 7. Verify on two countries; write `hoi4rec/<x>.py`, hook it
into a recorder, document the offsets in `docs/game-layouts.md`.
