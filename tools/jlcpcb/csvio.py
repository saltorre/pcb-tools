"""Thin CSV read/write helpers shared by the conversion steps."""

import csv


def read_table(path):
    """Return (fieldnames, rows) from a CSV file.

    Uses utf-8-sig because Fusion writes a UTF-8 byte-order mark that would
    otherwise become part of the first column's name.
    """
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, list(reader)


def write_table(path, fieldnames, rows):
    """Write rows (a list of dicts) to a CSV file with the given header order."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
