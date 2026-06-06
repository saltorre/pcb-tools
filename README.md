# pcb-tools

Scripts and tools for working with PCB suppliers.

Each supplier gets its own folder under [`tools/`](tools/). Today that's
[JLCPCB](tools/jlcpcb/).

## JLCPCB

Prepare Autodesk Fusion (Electronics / EAGLE) BOM and pick-and-place exports for
JLCPCB SMT assembly:

- **`convert.py`** — drops do-not-populate parts, renames columns to JLCPCB's
  format, merges the front/back placement files into one, fills LCSC part
  numbers per designator, and names the outputs for upload.
- **`jlcpcb-lookup`** (Claude skill) — resolves manufacturer part numbers (MPNs)
  to LCSC/JLCPCB codes and fills the BOM's `LCSC_PART_NUMBER` column.

Quick start:

```bash
python -m tools.jlcpcb.convert \
  --bom boards/<board>_LAYOUT.csv \
  --cpl boards/PnP_<board>_front.csv
```

This writes `bom_<board>_jlcpcb.csv` and the combined `PnP_<board>_jlcpcb.csv`
ready to upload. See [`tools/jlcpcb/README.md`](tools/jlcpcb/README.md) for the
full workflow, expected columns, and the LCSC lookup step.

## Working files

Put your board exports in [`boards/`](boards/) — it's git-ignored, since BOM and
placement files are private customer data and this is a public repo.

## Development

```bash
pip install -e ".[dev]"   # install the package and dev dependencies
pytest                    # run the tests
```

Requires Python 3.9+. The runtime is standard-library only; `pytest` is the lone
dev dependency.

## License

[GPL-3.0-or-later](LICENSE).
