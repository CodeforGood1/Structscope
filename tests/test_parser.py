from pathlib import Path

from parser_c import parse_structs
from parser_rust import parse_structs_rust


FIXTURES = Path(__file__).parent / "fixtures"


def test_c_struct_with_three_fields_parses_names():
    source = (FIXTURES / "sample_c.h").read_text(encoding="utf-8")
    structs = parse_structs(source, "c")
    by_name = {struct["name"]: struct for struct in structs}
    assert "FourByteFields" in by_name
    assert [field["name"] for field in by_name["FourByteFields"]["fields"]] == ["a", "b", "c"]


def test_typedef_struct_detected():
    source = (FIXTURES / "sample_c.h").read_text(encoding="utf-8")
    structs = parse_structs(source, "c")
    assert any(struct["name"] == "AliasStruct" for struct in structs)


def test_rust_struct_parses_field_names_and_types():
    source = (FIXTURES / "sample_rust.rs").read_text(encoding="utf-8")
    structs = parse_structs_rust(source)
    by_name = {struct["name"]: struct for struct in structs}
    assert "RustMixed" in by_name
    assert [(field["name"], field["raw_type"]) for field in by_name["RustMixed"]["fields"]] == [
        ("tag", "u8"),
        ("value", "f64"),
        ("state", "u8"),
    ]
