from analyser import analyse
from layout_engine import compute_layout
from platforms import PLATFORMS


def test_waste_ratio_between_zero_and_one():
    fields = [
        {"name": "a", "type": "char", "size": 1, "alignment": 1},
        {"name": "b", "type": "double", "size": 8, "alignment": 8},
    ]
    layout = compute_layout(fields, PLATFORMS["x86_64"])
    result = analyse(layout, "x86_64")
    assert 0.0 <= result["waste_ratio"] <= 1.0


def test_cache_line_splits_empty_for_small_struct():
    fields = [
        {"name": "a", "type": "int", "size": 4, "alignment": 4},
        {"name": "b", "type": "int", "size": 4, "alignment": 4},
    ]
    layout = compute_layout(fields, PLATFORMS["x86_64"])
    result = analyse(layout, "x86_64", 64)
    assert result["cache_line_splits"] == []


def test_cache_line_splits_non_empty_for_engineered_split():
    fields = [
        {"name": "prefix", "type": "char[60]", "size": 60, "alignment": 1},
        {"name": "span", "type": "u64ish", "size": 8, "alignment": 4},
    ]
    layout = compute_layout(fields, PLATFORMS["x86_64"])
    result = analyse(layout, "x86_64", 64)
    assert result["cache_line_splits"]
    assert result["cache_line_splits"][0]["field_name"] == "span"


def test_larger_than_cache_line_split_detected():
    fields = [
        {"name": "prefix", "type": "char[60]", "size": 60, "alignment": 1},
        {"name": "wide", "type": "wide", "size": 16, "alignment": 4},
    ]
    layout = compute_layout(fields, PLATFORMS["x86_64"])
    result = analyse(layout, "x86_64", 64)
    assert layout["total_size"] > 64
    assert result["cache_line_splits"][0]["field_name"] == "wide"


def test_waste_ratio_zero_for_no_padding():
    fields = [
        {"name": "a", "type": "int", "size": 4, "alignment": 4},
        {"name": "b", "type": "int", "size": 4, "alignment": 4},
    ]
    layout = compute_layout(fields, PLATFORMS["x86_64"])
    result = analyse(layout, "x86_64", 64)
    assert result["waste_ratio"] == 0.0
    assert result["waste_bytes"] == 0
