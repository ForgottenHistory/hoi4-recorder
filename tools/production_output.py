"""Equipment output per day, from a recording's daily country blocks (country/DAY.txt.gz).

    python tools/production_output.py RECORDING_DIR

Writes recordings/<name>/production_output.tsv: date, design (handle 70 id), stock, rate (units per day: the sum of
speed / cost over the design's lines), factories, lines; a row only when one of them changed. CountryLog writes the
same file live; this backfills older recordings. Names of the designs: equipment_designs.tsv / equipment.tsv.
Read it with: python tools/rows.py recordings/NAME production_output design=1329
"""
import glob
import gzip
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "hoi4-bridge", "client")]
from hoi4rec.countryrec import OUTPUT_COLS, output_rows


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recordings",
                       os.path.basename(os.path.normpath(src)))
    os.makedirs(out, exist_ok=True)
    last, n = {}, 0
    with open(os.path.join(out, "production_output.tsv"), "w", encoding="utf-8") as f:
        f.write("date\t" + "\t".join(OUTPUT_COLS) + "\n")
        for path in sorted(glob.glob(os.path.join(src, "country", "*.txt.gz"))):
            day = os.path.basename(path)[:10]
            with gzip.open(path, "rt", encoding="utf-8") as g:
                block = g.read()
            for row in output_rows(block):
                if last.get(row[0]) != row:
                    last[row[0]] = row
                    f.write(day + "\t" + "\t".join(row) + "\n")
                    n += 1
    print(f"{n} rows, {len(last)} designs -> {os.path.join(out, 'production_output.tsv')}")


if __name__ == "__main__":
    main()
