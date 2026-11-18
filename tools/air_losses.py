"""Air loss counters from a plaintext save (the air-zone panel's Days view).

    python tools/air_losses.py SAVE.hoi4 [TAG] [--days]

The save keeps, per country and air region, strategic_air/TAG/history/REGION/history_queue/0/data = 30 days x 89
columns (a ring buffer; the 'offset' above it is the write position). Verified on GER_1939_09_24_03.hoi4 (region 7):
col 3 = fighters lost in total (68), col 4 = shot down in air battle (60), col 6 = accident losses (8); cols 44/45
mirror the enemy's col 4 (the enemy fighters we shot down). Other columns belong to other channels (bombers, CAS...).
Channels are 7 columns wide: fighters c3 (total) c4 (air battle) c5 (AA) c6 (accident); tactical bombers c10-c13;
CAS c17-c20 (same order; bomber order verified 12 Oct 1939: panel 26 air battle / 43 AA / 5 accident vs memory 26 / 49 / 5). c39 = bombers disrupted, c44/c45 = enemy
fighters lost. Verified against the panel over Southern England (region 1), 5 Oct 1939 save.
Prints, per country and region, the 30-day sum of every non-zero column (--days: the per-day values too).
"""
import sys


def parse(path):
    """Yield (tag, region, offset, rows) where rows is a list of 30 lists of 89 numbers."""
    stack, tag, offset = [], None, None
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = iter(f)
        for line in lines:
            s = line.strip()
            if s.endswith("={"):
                stack.append(s[:-2])
            elif s == "}":
                if stack:
                    stack.pop()
            elif s.startswith("offset=") and len(stack) >= 3 and stack[-1] == "0" and stack[-2] == "history_queue":
                offset = int(s[7:])
            if s == "data={" and len(stack) >= 6 and stack[-2] == "0" and stack[-3] == "history_queue" \
                    and stack[-5] == "history" and "strategic_air" in stack:
                nums = [float(x) for x in next(lines).split() if x != "}"]
                if len(nums) == 30 * 89:
                    yield stack[stack.index("strategic_air") + 1], stack[-4], offset, \
                        [nums[i * 89:(i + 1) * 89] for i in range(30)]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    want = args[1] if len(args) > 1 else None
    for tag, region, offset, rows in parse(args[0]):
        if want and tag != want:
            continue
        sums = {c: sum(r[c] for r in rows) for c in range(89)}
        sums = {c: v for c, v in sums.items() if v}
        if not sums:
            continue
        print(f"{tag} region {region} offset {offset}: " + " ".join(f"c{c}={v:g}" for c, v in sums.items()))
        if "--days" in sys.argv:
            for c in sums:
                print(f"   c{c}: " + " ".join(f"{r[c]:g}" for r in rows))


if __name__ == "__main__":
    main()
