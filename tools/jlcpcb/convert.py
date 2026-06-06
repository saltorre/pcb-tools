"""Convert Fusion BOM and pick-and-place CSVs into JLCPCB-ready files.

Pipeline, given the two Fusion exports:

* Drop every part whose POPULATE cell is "0" from both files.
* In the BOM, rename the "Parts" column to "Designator" and guarantee an
  LCSC_PART_NUMBER column exists.
* Rename the pick-and-place columns to JLCPCB's names (Designator / Mid X /
  Mid Y / Rotation), add a Layer column, and copy each part's LCSC_PART_NUMBER
  into it, matched on reference designator.

The BOM is the source of truth: it decides which designators are populated and
which LCSC code each designator maps to. The pick-and-place file is filtered and
annotated from that information.

Board side comes from the pick-and-place filename: ``*_front.csv`` -> Top,
``*_back.csv`` -> Bottom. Fusion exports one placement file per side, and the
side isn't in the file's contents, so the filename is the only signal.
"""

import argparse
import os
import sys
from dataclasses import dataclass, field

from .columns import Columns
from .csvio import read_table, write_table
from .designators import expand_designators

# Fusion writes POPULATE as an integer-like string; treat these as do-not-populate.
_DNP_VALUES = {"0", "0.0"}

_OUTPUT_SUFFIX = "_jlcpcb"


def _is_dnp_value(value):
    return value.strip() in _DNP_VALUES


@dataclass
class BomIndex:
    """Designator-keyed view of the BOM: who is unpopulated, and each LCSC code."""

    dnp: set = field(default_factory=set)
    lcsc: dict = field(default_factory=dict)

    @classmethod
    def from_rows(cls, rows, columns):
        index = cls()
        for row in rows:
            index._add(row, columns)
        return index

    def _add(self, row, columns):
        populated = not _is_dnp_value(row.get(columns.populate, ""))
        part = (row.get(columns.lcsc, "") or "").strip()
        for ref in expand_designators(row.get(columns.bom_designators, "")):
            self._register(ref, populated, part)

    def _register(self, ref, populated, part):
        if not populated:
            self.dnp.add(ref)
        elif part:
            self.lcsc[ref] = part

    def is_dnp(self, ref):
        return ref in self.dnp

    def lcsc_for(self, ref):
        return self.lcsc.get(ref, "")


class Converter:
    """Transforms parsed BOM/pick-and-place tables into JLCPCB-ready tables.

    A table is the (fieldnames, rows) tuple returned by ``read_table``.
    """

    def __init__(self, columns=None):
        self.columns = columns or Columns()

    def convert(self, bom, cpl, layer="Top"):
        index = BomIndex.from_rows(bom[1], self.columns)
        return self._convert_bom(bom), self._convert_cpl(cpl, index, layer)

    def _convert_bom(self, bom):
        fieldnames, rows = bom
        kept = [self._transform_bom_row(row) for row in rows if self._is_populated(row)]
        return self._bom_fields(fieldnames), kept

    def _convert_cpl(self, cpl, index, layer):
        fieldnames, rows = cpl
        kept = [self._build_cpl_row(row, index, layer) for row in rows if self._keep_cpl(row, index)]
        return self._cpl_fields(fieldnames), kept

    def _is_populated(self, row):
        return not _is_dnp_value(row.get(self.columns.populate, ""))

    def _keep_cpl(self, row, index):
        ref = self._cpl_ref(row)
        return self._is_populated(row) and not index.is_dnp(ref)

    def _transform_bom_row(self, row):
        out = {self._renamed(key): value for key, value in row.items()}
        out.setdefault(self.columns.lcsc, "")
        return out

    def _build_cpl_row(self, row, index, layer):
        out = self._rename_cpl(row)
        out[self.columns.layer] = layer
        out[self.columns.lcsc] = index.lcsc_for(self._cpl_ref(row))
        return out

    def _rename_cpl(self, row):
        renames = self.columns.cpl_renames()
        return {renames.get(key, key): value for key, value in row.items()}

    def _bom_fields(self, fieldnames):
        renamed = [self._renamed(name) for name in fieldnames]
        return _with_column(renamed, self.columns.lcsc)

    def _cpl_fields(self, fieldnames):
        renames = self.columns.cpl_renames()
        out = [renames.get(name, name) for name in fieldnames]
        _with_column(out, self.columns.layer)
        return _with_column(out, self.columns.lcsc)

    def _renamed(self, name):
        # "Parts" -> "Designator"; every other column keeps its name.
        if name == self.columns.bom_designators:
            return self.columns.designator
        return name

    def _cpl_ref(self, row):
        return (row.get(self.columns.cpl_designator, "") or "").strip()


def _with_column(fieldnames, name):
    if name not in fieldnames:
        fieldnames.append(name)
    return fieldnames


def output_path(source, out_dir):
    """Default output path: ``<name>_jlcpcb.csv`` beside the source (or in out_dir)."""
    stem, ext = os.path.splitext(os.path.basename(source))
    directory = out_dir or os.path.dirname(os.path.abspath(source))
    return os.path.join(directory, f"{stem}{_OUTPUT_SUFFIX}{ext or '.csv'}")


def layer_for_filename(path):
    """Top for ``*_front.csv``, Bottom for ``*_back.csv``; None if neither."""
    name = os.path.basename(path).lower()
    if name.endswith("_front.csv"):
        return "Top"
    if name.endswith("_back.csv"):
        return "Bottom"
    return None


def resolve_layer(override, cpl_path):
    """Use an explicit --layer override, else infer from the filename (default Top)."""
    if override:
        return override
    inferred = layer_for_filename(cpl_path)
    if inferred is None:
        print(
            f"Warning: '{os.path.basename(cpl_path)}' does not end in _front.csv or "
            f"_back.csv; defaulting Layer to Top. Pass --layer to set it explicitly.",
            file=sys.stderr,
        )
        return "Top"
    return inferred


def require_columns(fieldnames, required, source):
    """Abort with a header-focused message if any required column is absent.

    A file exported without a header row has its first data row read as the
    header, so the expected column name is missing — that is the symptom this
    catches, steering the user to re-export with headers.
    """
    missing = [name for name in required if name not in fieldnames]
    if missing:
        raise SystemExit(_missing_columns_message(missing, fieldnames, source))


def _missing_columns_message(missing, fieldnames, source):
    found = ", ".join(fieldnames) if fieldnames else "(no columns)"
    return (
        f"{source}: missing required column(s): {', '.join(missing)}.\n"
        f"  Columns found: {found}\n"
        f"  If that row looks like component data rather than column names, the file "
        f"has no header row.\n"
        f"  Re-export it from Fusion WITH headers (the CSV's first row must name the columns)."
    )


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Convert Fusion BOM and pick-and-place CSVs for JLCPCB.")
    parser.add_argument("--bom", required=True, help="Path to the Fusion BOM CSV.")
    parser.add_argument("--cpl", required=True, help="Path to the Fusion pick-and-place (CPL) CSV.")
    parser.add_argument("--out-dir", default=None, help="Directory for outputs (default: beside each input).")
    parser.add_argument(
        "--layer",
        choices=["Top", "Bottom"],
        default=None,
        help="Board side for the placements (default: inferred from the _front/_back filename).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    columns = Columns()
    bom = read_table(args.bom)
    cpl = read_table(args.cpl)
    require_columns(bom[0], [columns.bom_designators], args.bom)
    require_columns(cpl[0], [columns.cpl_designator], args.cpl)

    layer = resolve_layer(args.layer, args.cpl)
    bom_out, cpl_out = Converter(columns).convert(bom, cpl, layer)

    bom_path = output_path(args.bom, args.out_dir)
    cpl_path = output_path(args.cpl, args.out_dir)
    write_table(bom_path, *bom_out)
    write_table(cpl_path, *cpl_out)

    print(f"BOM:             {len(bom_out[1])} parts -> {bom_path}")
    print(f"Pick-and-place:  {len(cpl_out[1])} placements -> {cpl_path}")


if __name__ == "__main__":
    main()
