from tools.jlcpcb.convert import BomIndex, Converter, output_path
from tools.jlcpcb.columns import Columns


def _bom():
    fields = ["Parts", "Value", "POPULATE", "LCSC_PART_NUMBER"]
    rows = [
        {"Parts": "C1, C2", "Value": "100nF", "POPULATE": "1", "LCSC_PART_NUMBER": "C49678"},
        {"Parts": "R1", "Value": "10k", "POPULATE": "0", "LCSC_PART_NUMBER": "C17414"},
        {"Parts": "U1", "Value": "MCU", "POPULATE": "1", "LCSC_PART_NUMBER": ""},
    ]
    return fields, rows


def _cpl():
    fields = ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]
    rows = [
        {"Designator": "C1", "Mid X": "1", "Mid Y": "2", "Layer": "Top", "Rotation": "0"},
        {"Designator": "C2", "Mid X": "3", "Mid Y": "4", "Layer": "Top", "Rotation": "90"},
        {"Designator": "R1", "Mid X": "5", "Mid Y": "6", "Layer": "Top", "Rotation": "0"},
        {"Designator": "U1", "Mid X": "7", "Mid Y": "8", "Layer": "Bottom", "Rotation": "180"},
    ]
    return fields, rows


def test_bom_renames_parts_to_designator_and_keeps_lcsc():
    (fields, rows) = Converter().convert(_bom(), _cpl())[0]
    assert "Designator" in fields and "Parts" not in fields
    assert "LCSC_PART_NUMBER" in fields
    assert rows[0]["Designator"] == "C1, C2"


def test_bom_drops_unpopulated_parts():
    (_, rows) = Converter().convert(_bom(), _cpl())[0]
    designators = [row["Designator"] for row in rows]
    assert "R1" not in designators  # POPULATE == 0
    assert len(rows) == 2


def test_cpl_drops_unpopulated_designators():
    (_, rows) = Converter().convert(_bom(), _cpl())[1]
    designators = [row["Designator"] for row in rows]
    assert designators == ["C1", "C2", "U1"]  # R1 removed


def test_cpl_gets_lcsc_by_designator():
    (fields, rows) = Converter().convert(_bom(), _cpl())[1]
    assert "LCSC_PART_NUMBER" in fields
    by_ref = {row["Designator"]: row["LCSC_PART_NUMBER"] for row in rows}
    assert by_ref["C1"] == "C49678"
    assert by_ref["C2"] == "C49678"  # shared BOM line
    assert by_ref["U1"] == ""  # no LCSC in BOM, left blank


def test_bom_index_tracks_dnp_and_lcsc():
    index = BomIndex.from_rows(_bom()[1], Columns())
    assert index.is_dnp("R1")
    assert not index.is_dnp("C1")
    assert index.lcsc_for("C2") == "C49678"
    assert index.lcsc_for("U1") == ""


def test_output_path_adds_suffix(tmp_path):
    src = str(tmp_path / "bom.csv")
    assert output_path(src, None).endswith("bom_jlcpcb.csv")
    assert output_path(src, "/out") == "/out/bom_jlcpcb.csv"
