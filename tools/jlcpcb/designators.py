"""Reference-designator parsing.

Fusion's BOM packs every designator for a line item into one cell (e.g.
"C1, C2, C3"), while the pick-and-place file lists one per row. Expanding the
BOM cell lets us key both files on individual designators.
"""

import re

# Designators are separated by commas and/or whitespace in Fusion exports.
_SEPARATORS = re.compile(r"[,\s]+")


def expand_designators(raw):
    """Split a packed designator cell into a list of individual designators."""
    if not raw:
        return []
    return [token for token in _SEPARATORS.split(raw.strip()) if token]
