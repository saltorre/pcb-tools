"""Convert Fusion BOM and pick-and-place CSVs into JLCPCB-ready files.

Pipeline, given the two Fusion exports:

* Drop every part whose POPULATE cell is "0" from both files.
* In the BOM, rename the "Parts" column to "Designator" and guarantee an
  LCSC_PART_NUMBER column exists.
* Copy each part's LCSC_PART_NUMBER into the pick-and-place file, matched on
  reference designator, so the placement file carries the JLCPCB part numbers.

The BOM is the source of truth: it decides which designators are populated and
which LCSC code each designator maps to. The pick-and-place file is filtered and
annotated from that information.
"""

import argparse
import os
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

    def convert(self, bom, cpl):
        index = BomIndex.from_rows(bom[1], self.columns)
        return self._convert_bom(bom), self._convert_cpl(cpl, index)

    def _convert_bom(self, bom):
        fieldnames, rows = bom
        kept = [self._transform_bom_row(row) for row in rows if self._is_populated(row)]
        return self._bom_fields(fieldnames), kept

    def _convert_cpl(self, cpl, index):
        fieldnames, rows = cpl
        kept = [self._annotate_cpl_row(row, index) for row in rows if self._keep_cpl(row, index)]
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

    def _annotate_cpl_row(self, row, index):
        out = dict(row)
        out[self.columns.lcsc] = index.lcsc_for(self._cpl_ref(row))
        return out

    def _bom_fields(self, fieldnames):
        renamed = [self._renamed(name) for name in fieldnames]
        return _with_column(renamed, self.columns.lcsc)

    def _cpl_fields(self, fieldnames):
        return _with_column(list(fieldnames), self.columns.lcsc)

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


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Convert Fusion BOM and pick-and-place CSVs for JLCPCB.")
    parser.add_argument("--bom", required=True, help="Path to the Fusion BOM CSV.")
    parser.add_argument("--cpl", required=True, help="Path to the Fusion pick-and-place (CPL) CSV.")
    parser.add_argument("--out-dir", default=None, help="Directory for outputs (default: beside each input).")
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    bom_out, cpl_out = Converter().convert(read_table(args.bom), read_table(args.cpl))

    bom_path = output_path(args.bom, args.out_dir)
    cpl_path = output_path(args.cpl, args.out_dir)
    write_table(bom_path, *bom_out)
    write_table(cpl_path, *cpl_out)

    print(f"BOM:             {len(bom_out[1])} parts -> {bom_path}")
    print(f"Pick-and-place:  {len(cpl_out[1])} placements -> {cpl_path}")


if __name__ == "__main__":
    main()
