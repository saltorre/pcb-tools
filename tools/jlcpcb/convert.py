"""Convert Fusion BOM and pick-and-place CSVs into JLCPCB-ready files.

Pipeline, given the two Fusion exports:

* Drop every part whose POPULATE cell is "0" from both files.
* In the BOM, rename the "Parts" column to "Designator" and guarantee an
  LCSC_PART_NUMBER column exists.
* Rename the pick-and-place columns to JLCPCB's names (Designator / Mid X /
  Mid Y / Rotation), add a Layer column, and copy each part's LCSC_PART_NUMBER
  into it, matched on reference designator.

The BOM is the source of truth: it decides which designators are populated and
which LCSC code each designator maps to. The pick-and-place files are filtered
and annotated from that information.

Fusion exports one placement file per board side, named ``*_front.csv`` and
``*_back.csv``; the side isn't in the file's contents, so the filename is the
only signal (front -> Top, back -> Bottom). Pass either one and the matching
opposite-side file beside it is picked up automatically; the two are merged into
a single JLCPCB placement file with a Layer column distinguishing them.

Outputs are named for JLCPCB upload: ``bom_<name>_jlcpcb.csv`` and the combined
``PnP_<name>_jlcpcb.csv`` (the ``_front``/``_back`` side suffix dropped).
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

    def convert(self, bom, cpls):
        """Convert one BOM and one or more (cpl_table, layer) pairs.

        Every placement file is filtered/annotated against the same BOM and the
        results are concatenated into a single combined placement table.
        """
        index = BomIndex.from_rows(bom[1], self.columns)
        return self._convert_bom(bom), self._convert_cpls(cpls, index)

    def _convert_bom(self, bom):
        fieldnames, rows = bom
        kept = [self._transform_bom_row(row) for row in rows if self._is_populated(row)]
        return self._bom_fields(fieldnames), kept

    def _convert_cpls(self, cpls, index):
        rows = []
        for cpl, layer in cpls:
            rows += self._cpl_rows(cpl, index, layer)
        return self.columns.cpl_output_fields(), rows

    def _cpl_rows(self, cpl, index, layer):
        return [self._build_cpl_row(row, index, layer) for row in cpl[1] if self._keep_cpl(row, index)]

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
        # Emit only JLCPCB's placement columns (plus LCSC), in cpl_output_fields order.
        out = {out_col: row.get(in_col, "") for in_col, out_col in self.columns.cpl_renames().items()}
        out[self.columns.layer] = layer
        out[self.columns.lcsc] = index.lcsc_for(self._cpl_ref(row))
        return out

    def _bom_fields(self, fieldnames):
        renamed = [self._renamed(name) for name in fieldnames]
        return _with_column(renamed, self.columns.lcsc)

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


# Board-side suffixes Fusion appends to placement filenames, and the layer each maps to.
_SIDES = {"_front": "Top", "_back": "Bottom"}


def _strip_side(stem):
    for side in _SIDES:
        if stem.lower().endswith(side):
            return stem[: -len(side)]
    return stem


def _in_dir(filename, source, out_dir):
    directory = out_dir or os.path.dirname(os.path.abspath(source))
    return os.path.join(directory, filename)


def bom_output_path(source, out_dir):
    """``bom_<name>_jlcpcb.csv`` beside the source (or in out_dir)."""
    stem, ext = os.path.splitext(os.path.basename(source))
    return _in_dir(f"bom_{stem}{_OUTPUT_SUFFIX}{ext or '.csv'}", source, out_dir)


def cpl_output_path(source, out_dir):
    """``<name>_jlcpcb.csv`` with the _front/_back side suffix dropped (combined file)."""
    stem, ext = os.path.splitext(os.path.basename(source))
    return _in_dir(f"{_strip_side(stem)}{_OUTPUT_SUFFIX}{ext or '.csv'}", source, out_dir)


def layer_for_filename(path):
    """Top for ``*_front.csv``, Bottom for ``*_back.csv``; None if neither."""
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    for side, layer in _SIDES.items():
        if stem.endswith(side):
            return layer
    return None


def cpl_layer(path):
    """Layer for a placement file, defaulting to Top (with a warning) if no side suffix."""
    inferred = layer_for_filename(path)
    if inferred is None:
        print(
            f"Warning: '{os.path.basename(path)}' has no _front/_back suffix; "
            f"using Layer=Top.",
            file=sys.stderr,
        )
        return "Top"
    return inferred


def sibling_cpl(path):
    """The matching opposite-side placement file beside ``path``, if it exists."""
    stem, ext = os.path.splitext(os.path.basename(path))
    base = _strip_side(stem)
    if base == stem:
        return None  # no _front/_back suffix, so there is no sibling to pair with
    present = stem[len(base):].lower()  # "_front" or "_back"
    other = "_back" if present == "_front" else "_front"
    candidate = os.path.join(os.path.dirname(path), f"{base}{other}{ext}")
    return candidate if os.path.exists(candidate) else None


def collect_cpl_paths(cpl_path):
    """The given placement file plus its auto-found opposite-side sibling (if any)."""
    sibling = sibling_cpl(cpl_path)
    return [cpl_path, sibling] if sibling else [cpl_path]


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
    parser.add_argument(
        "--cpl",
        required=True,
        help="Path to a Fusion pick-and-place CSV (_front or _back); the other side is found automatically.",
    )
    parser.add_argument("--out-dir", default=None, help="Directory for outputs (default: beside each input).")
    return parser.parse_args(argv)


def _load_cpls(cpl_arg, columns):
    """Read the placement file and its sibling into (path, table, layer) tuples."""
    loaded = []
    for path in collect_cpl_paths(cpl_arg):
        table = read_table(path)
        require_columns(table[0], [columns.cpl_designator], path)
        loaded.append((path, table, cpl_layer(path)))
    return loaded


def main(argv=None):
    args = _parse_args(argv)
    columns = Columns()
    bom = read_table(args.bom)
    require_columns(bom[0], [columns.bom_designators], args.bom)

    cpls = _load_cpls(args.cpl, columns)
    bom_out, cpl_out = Converter(columns).convert(bom, [(table, layer) for _, table, layer in cpls])

    bom_path = bom_output_path(args.bom, args.out_dir)
    cpl_path = cpl_output_path(args.cpl, args.out_dir)
    write_table(bom_path, *bom_out)
    write_table(cpl_path, *cpl_out)

    print(f"BOM:             {len(bom_out[1])} parts -> {bom_path}")
    print(f"Pick-and-place:  {len(cpl_out[1])} placements -> {cpl_path}")
    for path, _, layer in cpls:
        print(f"    {layer:<6} <- {os.path.basename(path)}")


if __name__ == "__main__":
    main()
