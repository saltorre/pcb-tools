import pytest

from tools.jlcpcb.convert import (
    BomIndex,
    Converter,
    bom_output_path,
    collect_cpl_paths,
    cpl_layer,
    cpl_output_path,
    layer_for_filename,
    require_columns,
    sibling_cpl,
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


def _cpl(designators=("C1", "C2", "R1", "U1")):
    # Mirrors Fusion's pick-and-place export: designator column is "Name".
    fields = ["Name", "X", "Y", "Angle", "Value", "Package"]
    rows = [{"Name": d, "X": "1", "Y": "2", "Angle": "0", "Value": "v", "Package": "0402"} for d in designators]
    return fields, rows


def _cpls(layer="Top"):
    return [(_cpl(), layer)]


def test_bom_renames_parts_to_designator_and_keeps_lcsc():
    (fields, rows) = Converter().convert(_bom(), _cpls())[0]
    assert "Designator" in fields and "Parts" not in fields
    assert "LCSC_PART_NUMBER" in fields
    assert rows[0]["Designator"] == "C1, C2"


def test_bom_drops_unpopulated_parts():
    (_, rows) = Converter().convert(_bom(), _cpls())[0]
    designators = [row["Designator"] for row in rows]
    assert "R1" not in designators  # POPULATE == 0
    assert len(rows) == 2


def test_cpl_output_is_jlcpcb_columns_in_exact_order():
    (fields, _) = Converter().convert(_bom(), _cpls())[1]
    assert fields == ["Designator", "Mid X", "Mid Y", "Layer", "Rotation", "LCSC_PART_NUMBER"]
    # Fusion's extra placement columns are dropped from the JLCPCB output.
    assert "Value" not in fields and "Package" not in fields


def test_cpl_drops_unpopulated_designators():
    (_, rows) = Converter().convert(_bom(), _cpls())[1]
    designators = [row["Designator"] for row in rows]
    assert designators == ["C1", "C2", "U1"]  # R1 removed


def test_cpl_gets_lcsc_by_designator():
    (fields, rows) = Converter().convert(_bom(), _cpls())[1]
    assert "LCSC_PART_NUMBER" in fields
    by_ref = {row["Designator"]: row["LCSC_PART_NUMBER"] for row in rows}
    assert by_ref["C1"] == "C49678"
    assert by_ref["C2"] == "C49678"  # shared BOM line
    assert by_ref["U1"] == ""  # no LCSC in BOM, left blank


def test_cpl_adds_layer_per_file():
    (fields, rows) = Converter().convert(_bom(), _cpls("Bottom"))[1]
    assert "Layer" in fields
    assert all(row["Layer"] == "Bottom" for row in rows)


def test_combines_front_and_back_into_one_table_with_layers():
    front = (_cpl(("C1", "C2")), "Top")
    back = (_cpl(("U1",)), "Bottom")
    (_, rows) = Converter().convert(_bom(), [front, back])[1]
    by_ref = {row["Designator"]: row["Layer"] for row in rows}
    assert by_ref == {"C1": "Top", "C2": "Top", "U1": "Bottom"}


def test_layer_inferred_from_filename():
    assert layer_for_filename("PnP_board_front.csv") == "Top"
    assert layer_for_filename("PnP_board_back.csv") == "Bottom"
    assert layer_for_filename("PnP_board.csv") is None


def test_cpl_layer_defaults_to_top_without_suffix():
    assert cpl_layer("PnP_board_back.csv") == "Bottom"
    assert cpl_layer("PnP_board.csv") == "Top"  # warns, but still usable


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


def test_bom_output_path_adds_prefix_and_suffix(tmp_path):
    src = str(tmp_path / "PCB1001M1_LAYOUT.csv")
    assert bom_output_path(src, None).endswith("bom_PCB1001M1_LAYOUT_jlcpcb.csv")
    assert bom_output_path(src, "/out") == "/out/bom_PCB1001M1_LAYOUT_jlcpcb.csv"


def test_cpl_output_path_strips_side_suffix(tmp_path):
    src = str(tmp_path / "PnP_PCB1001M1_Layout_front.csv")
    assert cpl_output_path(src, "/out") == "/out/PnP_PCB1001M1_Layout_jlcpcb.csv"


def test_sibling_and_collect_find_the_other_side(tmp_path):
    front = tmp_path / "PnP_board_front.csv"
    back = tmp_path / "PnP_board_back.csv"
    front.write_text("Name\nC1\n")
    back.write_text("Name\nU1\n")
    assert sibling_cpl(str(front)) == str(back)
    assert collect_cpl_paths(str(front)) == [str(front), str(back)]


def test_sibling_returns_none_when_no_back(tmp_path):
    front = tmp_path / "PnP_board_front.csv"
    front.write_text("Name\nC1\n")
    assert sibling_cpl(str(front)) is None
    assert collect_cpl_paths(str(front)) == [str(front)]
