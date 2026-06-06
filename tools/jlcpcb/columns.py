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
    # One row per placed component. Fusion labels these columns; the output uses
    # JLCPCB's expected names (Designator / Mid X / Mid Y / Rotation).
    cpl_designator: str = "Name"
    cpl_x: str = "X"
    cpl_y: str = "Y"
    cpl_rotation: str = "Angle"

    # --- JLCPCB pick-and-place output names ---
    out_mid_x: str = "Mid X"
    out_mid_y: str = "Mid Y"
    out_rotation: str = "Rotation"
    layer: str = "Layer"

    def cpl_renames(self):
        """Map Fusion pick-and-place input columns to JLCPCB output names."""
        return {
            self.cpl_designator: self.designator,
            self.cpl_x: self.out_mid_x,
            self.cpl_y: self.out_mid_y,
            self.cpl_rotation: self.out_rotation,
        }

    def cpl_output_fields(self):
        """JLCPCB placement columns, in JLCPCB's expected order.

        LCSC_PART_NUMBER is appended last: JLCPCB doesn't require it in the CPL,
        but carrying it through makes the placement file easier to read.
        """
        return [
            self.designator,
            self.out_mid_x,
            self.out_mid_y,
            self.layer,
            self.out_rotation,
            self.lcsc,
        ]
