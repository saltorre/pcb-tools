# JLCPCB tools

Prepare Autodesk Fusion (Electronics / EAGLE) exports for JLCPCB SMT assembly.

Two pieces:

| Step | What | How |
| --- | --- | --- |
| Look up LCSC part numbers | Resolve manufacturer part numbers (MPNs) to JLCPCB/LCSC codes and fill the BOM's `LCSC_PART_NUMBER` column | `jlcpcb-lookup` Claude skill |
| Convert BOM + pick-and-place | Drop unpopulated parts, rename columns, propagate LCSC codes to the placement file | `convert.py` script |

## Expected Fusion columns

The defaults assume these headers (override them in
[`columns.py`](columns.py) if your library uses different attribute names):

- **BOM:** `Parts` (designators, e.g. `C1, C2`), `POPULATE` (`0` = do-not-populate),
  `MPN`, `LCSC_PART_NUMBER`
- **Pick-and-place:** `Designator` (one component per row)

`POPULATE` and `LCSC_PART_NUMBER` are custom library attributes — add them to your
Fusion device attributes if they aren't there yet.

## 1. Fill in LCSC part numbers (Claude skill)

In Claude Code, point the skill at your exported BOM:

```text
Use jlcpcb-lookup on ~/Desktop/myboard_bom.csv
```

It reads each part's `MPN`, looks the part up on LCSC, and writes the `Cxxxxx`
code into `LCSC_PART_NUMBER`. Existing codes are left untouched; anything it
can't confidently resolve is left blank and reported so you can fill it by hand.

Run this **before** the conversion step so the placement file inherits the codes.

## 2. Convert the BOM and pick-and-place files

```bash
python -m tools.jlcpcb.convert \
  --bom ~/Desktop/myboard_bom.csv \
  --cpl ~/Desktop/myboard_pnp.csv
```

By default each output is written next to its input as `<name>_jlcpcb.csv`; pass
`--out-dir DIR` to collect them elsewhere.

What it does:

- Removes every part whose `POPULATE` is `0` from **both** files.
- Renames the BOM's `Parts` column to `Designator` and ensures a
  `LCSC_PART_NUMBER` column exists.
- Copies each part's `LCSC_PART_NUMBER` into the pick-and-place file, matched on
  reference designator.

Upload the two `_jlcpcb.csv` files to JLCPCB's assembly order page. If JLCPCB's
column auto-detection doesn't pick up `LCSC_PART_NUMBER`, map it to "LCSC Part #"
in their import dialog.

## Development

```bash
pip install -e ".[dev]"   # from the repo root
pytest                    # run the tests
```
