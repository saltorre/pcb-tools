# JLCPCB tools

Prepare Autodesk Fusion (Electronics / EAGLE) exports for JLCPCB SMT assembly.

Two pieces:

| Step | What | How |
| --- | --- | --- |
| Look up LCSC part numbers | Resolve manufacturer part numbers (MPNs) to JLCPCB/LCSC codes and fill the BOM's `LCSC_PART_NUMBER` column | `jlcpcb-lookup` Claude skill |
| Convert BOM + pick-and-place | Drop unpopulated parts, rename columns, propagate LCSC codes to the placement file | `convert.py` script |

## Where to put your files

Drop your Fusion exports in the repo's [`boards/`](../../boards) folder and run
the tool against them; the `_jlcpcb.csv` outputs land there too, beside each
input. Everything in `boards/` is git-ignored — board CSVs are private customer
data and never get committed. (For one folder per board, make a subfolder like
`boards/PCB1001M1/`.)

## Expected Fusion columns

The defaults assume these headers (override them in
[`columns.py`](columns.py) if your library uses different attribute names):

- **BOM:** `Parts` (designators, e.g. `C1, C2`), `POPULATE` (`0` = do-not-populate),
  `MPN`, `LCSC_PART_NUMBER`
- **Pick-and-place:** `Name` (one component per row), `X`, `Y`, `Angle`

`POPULATE` and `LCSC_PART_NUMBER` are custom library attributes — add them to your
Fusion device attributes if they aren't there yet.

**Export with headers.** Both CSVs must have a header row naming the columns. If
the pick-and-place file is missing its header, the converter stops and tells you
to re-export — it keys on column names, not position.

**Two board sides.** Fusion exports one placement file per side, already named
`..._front.csv` and `..._back.csv`. Pass either one to `--cpl`; the tool finds
the matching opposite-side file beside it automatically and merges both into a
single placement file, setting the `Layer` column from each filename (`front` →
`Top`, `back` → `Bottom`). A single-sided board just has the one file.

## 1. Fill in LCSC part numbers (Claude skill)

In Claude Code, point the skill at your exported BOM:

```text
Use jlcpcb-lookup on boards/myboard_bom.csv
```

It reads each part's `MPN`, looks the part up on LCSC, and writes the `Cxxxxx`
code into `LCSC_PART_NUMBER`. Existing codes are left untouched; anything it
can't confidently resolve is left blank and reported so you can fill it by hand.

Run this **before** the conversion step so the placement file inherits the codes.

## 2. Convert the BOM and pick-and-place files

```bash
python -m tools.jlcpcb.convert \
  --bom boards/PCB1001M1_LAYOUT.csv \
  --cpl boards/PnP_PCB1001M1_Layout_front.csv
```

This writes two files beside the inputs (use `--out-dir DIR` to collect them
elsewhere):

- `bom_PCB1001M1_LAYOUT_jlcpcb.csv` — the BOM, with a `bom_` prefix so it's
  obviously the BOM at upload time.
- `PnP_PCB1001M1_Layout_jlcpcb.csv` — front and back placements merged (the
  `_front`/`_back` side suffix dropped).

What it does:

- Removes every part whose `POPULATE` is `0` from **both** files.
- BOM: renames `Parts` → `Designator`, ensures a `LCSC_PART_NUMBER` column exists,
  and keeps the other columns (including `MPN`) untouched.
- Pick-and-place: emits exactly JLCPCB's placement columns, in order —
  `Designator, Mid X, Mid Y, Layer, Rotation` (mapped from Fusion's
  `Name`/`X`/`Y`/`Angle` + the side-derived `Layer`) — with `LCSC_PART_NUMBER`
  appended (filled per designator from the BOM). Fusion's `Value`/`Package`
  columns are dropped. JLCPCB ignores the trailing `LCSC_PART_NUMBER`; it's there
  for readability.

Upload the two `_jlcpcb.csv` files to JLCPCB's assembly order page. If JLCPCB's
column auto-detection doesn't pick up `LCSC_PART_NUMBER`, map it to "LCSC Part #"
in their import dialog.

## Development

```bash
pip install -e ".[dev]"   # from the repo root
pytest                    # run the tests
```
