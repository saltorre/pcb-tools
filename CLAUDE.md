# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

"Scripts and Tools for Working with PCB Suppliers" (`README.md`). Each supplier
gets its own folder under `tools/`. Currently: JLCPCB.

## Commands

Python project, packaged with `pyproject.toml` (stdlib-only runtime; `pytest` is
the only dev dependency). From the repo root:

```bash
pip install -e ".[dev]"        # install package + dev deps
pytest                          # run all tests
pytest tools/jlcpcb/tests/test_convert.py::test_bom_drops_unpopulated_parts  # single test
# Run a CLI tool (pass the _front placement file; the _back is found automatically):
python -m tools.jlcpcb.convert --bom boards/<board>.csv --cpl boards/PnP_<board>_front.csv
```

Run CLI tools as modules (`python -m tools.jlcpcb.convert`), not as file paths —
the package uses relative imports.

## Architecture

`tools/jlcpcb/` converts Autodesk Fusion BOM and pick-and-place CSV exports into
JLCPCB SMT-assembly format. Two distinct mechanisms, by design:

- **Conversion is a deterministic script** (`convert.py`). The BOM is the source
  of truth: `BomIndex` reads it once to learn which reference designators are
  do-not-populate (`POPULATE == 0`) and which LCSC part number each maps to.
  `Converter` then drops DNP parts from every file, renames the BOM's `Parts`
  column to `Designator`, merges the front/back placement files into one table
  (a `Layer` column — Top/Bottom — inferred from each filename's `_front`/`_back`
  suffix), and emits the placement file as JLCPCB's exact ordered column set
  (`Columns.cpl_output_fields()`) with each LCSC code matched in by designator.
  `main()` reads inputs, validates required headers (`require_columns`, which
  catches header-less exports), and writes `bom_<name>_jlcpcb.csv` plus the
  combined `PnP_<name>_jlcpcb.csv`.
- **MPN → LCSC lookup is a Claude skill**, not a script
  (`.claude/skills/jlcpcb-lookup/`). It resolves manufacturer part numbers to
  LCSC codes via web search rather than scraping an unofficial API. The skill
  fills the BOM's `LCSC_PART_NUMBER` column; conversion must run *after* it so
  the placement file inherits the codes.

Supporting modules: `columns.py` holds all input/output column names and the
rename/output-order maps, so a project with different Fusion attribute headers
overrides config, not logic; `designators.py` expands packed cells (`"C1, C2"`)
into individual designators; `csvio.py` wraps CSV read/write (utf-8-sig to absorb
Fusion's byte-order mark). See `tools/jlcpcb/README.md` for the end-user workflow.

## Conventions

- **Board data is private.** BOM/placement CSVs are customer data and this is a
  public repo. They live in the git-ignored `boards/` folder; the root
  `.gitignore` also ignores `/*.csv` as a safety net. Never commit a board CSV.
- GPL v3 — new source files must stay compatible.
- The global coding standards in `~/.claude/CLAUDE.md` apply (≤3 params per
  function, ≤2 nesting levels, reuse over duplication, unit tests for new code,
  comments explain "why"). The existing `tools/jlcpcb/` code follows these.
