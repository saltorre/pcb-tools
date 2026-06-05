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
python -m tools.jlcpcb.convert --bom BOM.csv --cpl PNP.csv   # run a CLI tool
```

Run CLI tools as modules (`python -m tools.jlcpcb.convert`), not as file paths —
the package uses relative imports.

## Architecture

`tools/jlcpcb/` converts Autodesk Fusion BOM and pick-and-place CSV exports into
JLCPCB SMT-assembly format. Two distinct mechanisms, by design:

- **Conversion is a deterministic script** (`convert.py`). The BOM is the source
  of truth: `BomIndex` reads it once to learn which reference designators are
  do-not-populate (`POPULATE == 0`) and which LCSC part number each maps to;
  `Converter` then filters both files and copies LCSC codes into the
  pick-and-place file by designator. Column names live in `columns.py` so a
  project with different Fusion attribute headers overrides config, not logic.
  `designators.py` expands packed cells (`"C1, C2"`) into individual designators;
  `csvio.py` wraps CSV read/write (utf-8-sig to absorb Fusion's BOM marker).
- **MPN → LCSC lookup is a Claude skill**, not a script
  (`.claude/skills/jlcpcb-lookup/`). It resolves manufacturer part numbers to
  LCSC codes via web search rather than scraping an unofficial API. The skill
  fills the BOM's `LCSC_PART_NUMBER` column; conversion must run *after* it so
  the placement file inherits the codes.

See `tools/jlcpcb/README.md` for the end-user workflow.

## Conventions

- GPL v3 — new source files must stay compatible.
- The global coding standards in `~/.claude/CLAUDE.md` apply (≤3 params per
  function, ≤2 nesting levels, reuse over duplication, unit tests for new code,
  comments explain "why"). The existing `tools/jlcpcb/` code follows these.
