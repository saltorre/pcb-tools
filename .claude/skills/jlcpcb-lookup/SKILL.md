---
name: jlcpcb-lookup
description: Resolve manufacturer part numbers (MPNs) to JLCPCB/LCSC part numbers (Cxxxxx) and write them into the LCSC_PART_NUMBER column of a Fusion BOM CSV. Use when the user wants to look up LCSC codes, fill in JLCPCB part numbers, or prepare a BOM for JLCPCB assembly.
---

# JLCPCB part-number lookup

Fill the `LCSC_PART_NUMBER` column of a BOM by looking up each part's
manufacturer part number (MPN) on LCSC. JLCPCB sources its assembly parts from
LCSC, so the JLCPCB part number is the LCSC code, formatted `C` followed by
digits (e.g. `C25804`).

Run this **before** `tools/jlcpcb/convert.py`, because `convert.py` copies the
BOM's `LCSC_PART_NUMBER` values into the pick-and-place file. Filling the BOM
first means the placements come out annotated.

## Inputs

- A BOM CSV path (Fusion export). Default columns: `MPN` for the manufacturer
  part number, `LCSC_PART_NUMBER` for the result. If the file uses different
  headers, ask the user or infer from the header row.

## Procedure

1. Read the BOM with the `Read` tool (or a quick Python snippet for large files)
   and find the `MPN` and `LCSC_PART_NUMBER` columns.
2. Collect the set of **unique** MPNs whose `LCSC_PART_NUMBER` cell is empty.
   Skip rows that already have a code — never overwrite an existing value.
3. For each unique MPN, find its LCSC code:
   - `WebSearch` / `WebFetch` against `https://www.lcsc.com/search?q=<MPN>` (and,
     if needed, the part's JLCPCB assembly page).
   - Confirm the manufacturer and full part number on the result page match the
     MPN — do not accept a near-match on a truncated number.
   - Read the LCSC code from the product page (shown as `LCSC Part #: Cxxxxx`).
   - Prefer parts that are in stock for JLCPCB assembly; when both a Basic and an
     Extended part match, note the Basic option to the user (it avoids a loading
     fee) but use whichever the user's MPN actually specifies.
4. Write the codes back into `LCSC_PART_NUMBER` for every row sharing that MPN.
   Leave the cell blank if you cannot confidently identify the part.

## Output

- Save the updated BOM (overwrite, or to `<name>_with_lcsc.csv` if the user
  prefers to keep the original).
- Report a summary: how many MPNs were resolved, and list any that were left
  blank with the reason, so the user can fill those manually.

## Notes

- Do the lookups in parallel where possible to stay fast.
- Never guess a code. A blank cell the user can fix is better than a wrong part
  number that gets soldered onto a board.
