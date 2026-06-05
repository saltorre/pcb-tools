from tools.jlcpcb.designators import expand_designators


def test_expands_comma_and_space_separated():
    assert expand_designators("C1, C2 C3,C4") == ["C1", "C2", "C3", "C4"]


def test_blank_and_none_yield_empty_list():
    assert expand_designators("") == []
    assert expand_designators(None) == []


def test_strips_surrounding_whitespace():
    assert expand_designators("  R1 ,  R2  ") == ["R1", "R2"]
