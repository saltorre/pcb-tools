import pytest

from tools.jlcpcb.convert import (
    BomIndex,
    Converter,
    layer_for_filename,
    output_path,
    require_columns,
)
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
    # Mirrors Fusion's pick-and-place export: designator column is "Name".
    fields = ["Name", "X", "Y", "Angle", "Value", "Package"]
    rows = [
        {"Name": "C1", "X": "1", "Y": "2", "Angle": "90", "Value": "100nF", "Package": "0402"},
        {"Name": "C2", "X": "3", "Y": "4", "Angle": "0", "Value": "100nF", "Package": "0402"},
        {"Name": "R1", "X": "5", "Y": "6", "Angle": "0", "Value": "10k", "Package": "0402"},
        {"Name": "U1", "X": "7", "Y": "8", "Angle": "180", "Value": "MCU", "Package": "QFN"},
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


def test_cpl_renames_columns_to_jlcpcb_names():
    (fields, _) = Converter().convert(_bom(), _cpl())[1]
    assert "Designator" in fields and "Name" not in fields
    assert "Mid X" in fields and "Mid Y" in fields
    assert "Rotation" in fields and "Angle" not in fields


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


def test_cpl_adds_layer_from_argument():
    (fields, rows) = Converter().convert(_bom(), _cpl(), "Bottom")[1]
    assert "Layer" in fields
    assert all(row["Layer"] == "Bottom" for row in rows)


def test_layer_inferred_from_filename():
    assert layer_for_filename("PnP_board_front.csv") == "Top"
    assert layer_for_filename("PnP_board_back.csv") == "Bottom"
    assert layer_for_filename("PnP_board.csv") is None


def test_bom_index_tracks_dnp_and_lcsc():
    index = BomIndex.from_rows(_bom()[1], Columns())
    assert index.is_dnp("R1")
    assert not index.is_dnp("C1")
    assert index.lcsc_for("C2") == "C49678"
    assert index.lcsc_for("U1") == ""


def test_require_columns_passes_when_present():
    require_columns(["Designator", "Mid X"], ["Designator"], "pnp.csv")  # no raise


def test_require_columns_errors_on_headerless_file():
    # A headerless pick-and-place file reads its first component row as the header.
    headerless = ["C1", "3.18", "22.86", "90.00"]
    with pytest.raises(SystemExit) as exc:
        require_columns(headerless, ["Designator"], "pnp.csv")
    message = str(exc.value)
    assert "Designator" in message
    assert "header" in message.lower()


def test_output_path_adds_suffix(tmp_path):
    src = str(tmp_path / "bom.csv")
    assert output_path(src, None).endswith("bom_jlcpcb.csv")
    assert output_path(src, "/out") == "/out/bom_jlcpcb.csv"
