"""
Import your own bearing catalogue data.

Usage (from the backend directory):
    python -m engineering.bearings.importer path/to/my_bearings.csv
    python -m engineering.bearings.importer path/to/my_bearings.csv --out data/user/bearings.csv

CSV columns (header row required):
    designation, type, d, D, B, C, C0, Pu, n_ref, n_lim       (required)
    e, Y, Y0, Y1, Y2, f0                                       (optional)

Units: d, D, B in mm; C, C0, Pu in kN; n_ref, n_lim in rpm.
type is one of: dgbb, acbb, crb, trb, sabb, srb, tbb
  (tapered roller rows need e, Y, Y0; self-aligning ball / spherical roller rows need
   e, Y1, Y2, Y0).

The validated file is written to backend/data/user/bearings.csv (git-ignored). It is
merged at start-up; a row overrides the built-in bearing with the same designation.
Use this for data you are licensed to use (e.g. an export from your supplier).
"""
import argparse
import csv
import os
import sys
from typing import Dict, List

from .data import OPTIONAL_COLUMNS, REQUIRED_COLUMNS, TYPES, USER_FILE, parse_user_row

_NEEDS = {"trb": ["e", "Y", "Y0"], "sabb": ["e", "Y1", "Y2", "Y0"], "srb": ["e", "Y1", "Y2", "Y0"]}


class ImportError_(ValueError):
    pass


def validate_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Return cleaned rows or raise ImportError_ listing every problem found."""
    errors: List[str] = []
    clean: List[Dict[str, str]] = []
    seen = set()
    for i, raw in enumerate(rows, start=2):  # header is line 1
        row = {k.strip(): (v or "").strip() for k, v in raw.items() if k}
        missing = [c for c in REQUIRED_COLUMNS if not row.get(c)]
        if missing:
            errors.append(f"line {i}: missing {', '.join(missing)}")
            continue
        t = row["type"].lower()
        if t not in TYPES:
            errors.append(f"line {i}: unknown type '{row['type']}' (use one of {', '.join(TYPES)})")
            continue
        try:
            nums = {c: float(row[c]) for c in REQUIRED_COLUMNS[2:]}
            for c in OPTIONAL_COLUMNS:
                if row.get(c):
                    float(row[c])
        except ValueError as e:
            errors.append(f"line {i}: non-numeric value ({e})")
            continue
        if any(v <= 0 for v in nums.values()):
            errors.append(f"line {i}: dimensions, ratings and speeds must be positive")
            continue
        if nums["D"] <= nums["d"]:
            errors.append(f"line {i}: D must be larger than d")
            continue
        need = [c for c in _NEEDS.get(t, []) if not row.get(c)]
        if need:
            errors.append(f"line {i}: type {t} needs {', '.join(need)}")
            continue
        key = row["designation"]
        if key in seen:
            errors.append(f"line {i}: duplicate designation '{key}'")
            continue
        seen.add(key)
        row["type"] = t
        clean.append({c: row.get(c, "") for c in REQUIRED_COLUMNS + OPTIONAL_COLUMNS})
    if errors:
        raise ImportError_("; ".join(errors))
    if not clean:
        raise ImportError_("no rows found")
    for r in clean:  # final round-trip through the loader
        parse_user_row(r)
    return clean


def import_csv(src: str, dest: str = USER_FILE) -> int:
    with open(src, newline="", encoding="utf-8-sig") as f:
        rows = validate_rows(list(csv.DictReader(f)))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Import a bearing CSV into MechPartner.")
    ap.add_argument("csv", help="source CSV file")
    ap.add_argument("--out", default=USER_FILE, help=f"destination (default {USER_FILE})")
    args = ap.parse_args(argv)
    try:
        n = import_csv(args.csv, args.out)
    except ImportError_ as e:
        print(f"Import failed: {e}", file=sys.stderr)
        return 1
    print(f"Imported {n} bearings into {args.out}. Restart the backend to load them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
