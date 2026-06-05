from tools.jlcpcb.csvio import read_table, write_table


def test_round_trip(tmp_path):
    path = str(tmp_path / "t.csv")
    fields = ["Designator", "LCSC_PART_NUMBER"]
    rows = [{"Designator": "C1", "LCSC_PART_NUMBER": "C49678"}]
    write_table(path, fields, rows)
    assert read_table(path) == (fields, rows)


def test_reads_utf8_bom_without_corrupting_first_header(tmp_path):
    # Fusion prepends a UTF-8 BOM; the first column name must stay clean.
    path = tmp_path / "t.csv"
    path.write_bytes("﻿Parts,Value\nC1,100nF\n".encode("utf-8"))
    fields, rows = read_table(str(path))
    assert fields[0] == "Parts"
    assert rows[0]["Parts"] == "C1"
