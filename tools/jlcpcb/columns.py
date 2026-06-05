"""Column-name configuration for Fusion exports and JLCPCB outputs.

Fusion lets each library define its own attribute names, so the columns a BOM or
pick-and-place export actually uses vary between projects. Keeping the names in
one configurable place means a project with different headers only overrides the
field instead of editing the conversion logic.
"""

from dataclasses import dataclass


@dataclass
class Columns:
    # --- Fusion BOM input ---
    # Fusion's default BOM groups reference designators under "Parts".
    bom_designators: str = "Parts"
    # Custom library attribute: "0" means do-not-populate.
    populate: str = "POPULATE"
    # Custom library attribute holding the LCSC/JLCPCB code (e.g. C25804).
    lcsc: str = "LCSC_PART_NUMBER"
    # Manufacturer part number, read by the jlcpcb-lookup skill.
    mpn: str = "MPN"

    # --- Output ---
    # JLCPCB expects per-part reference designators under "Designator".
    designator: str = "Designator"

    # --- Fusion pick-and-place input ---
    # One row per placed component; the reference designator column.
    cpl_designator: str = "Designator"
