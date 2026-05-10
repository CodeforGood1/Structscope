"""Tree-sitter based C/C++ struct and class extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from tree_sitter import Language, Parser

import tree_sitter_c
import tree_sitter_cpp

from layout_engine import compute_layout
from platforms import PLATFORMS


X86_64 = PLATFORMS["x86_64"]
QUALIFIERS = {
    "const",
    "volatile",
    "restrict",
    "__restrict",
    "__restrict__",
    "mutable",
    "static",
    "register",
    "extern",
    "auto",
    "constexpr",
    "inline",
}
DECLARATION_PUNCTUATION = {";", ",", ":", "{", "}"}


@dataclass
class ResolvedType:
    size: int
    alignment: int
    unresolved: bool = False


def _parser_for(language: str) -> Parser:
    if language == "c":
        grammar = tree_sitter_c.language()
    elif language == "cpp":
        grammar = tree_sitter_cpp.language()
    else:
        raise ValueError("language must be 'c' or 'cpp'")

    parser = Parser()
    parser.language = Language(grammar)
    return parser


def _text(node) -> str:
    return node.text.decode("utf-8", errors="replace")


def _walk(node) -> Iterable:
    yield node
    for child in node.children:
        yield from _walk(child)


def _named_child(node, *types: str):
    for child in node.children:
        if child.type in types:
            return child
    return None


def _normalise_type(raw_type: str) -> str:
    collapsed = " ".join(raw_type.replace("\t", " ").replace("\n", " ").split())
    tokens = [token for token in collapsed.split(" ") if token not in QUALIFIERS]
    return " ".join(tokens).strip()


def _declarator_name(declarator) -> str | None:
    if declarator is None:
        return None
    if declarator.type in {"field_identifier", "identifier", "type_identifier"}:
        return _text(declarator)
    for child in declarator.children:
        found = _declarator_name(child)
        if found:
            return found
    return None


def _is_function_member(declarator) -> bool:
    if declarator is None:
        return False
    return any(node.type in {"function_declarator", "parameter_list"} for node in _walk(declarator))


def _pointer_depth(declarator) -> int:
    if declarator is None:
        return 0
    return sum(1 for node in _walk(declarator) if node.type == "*")


def _array_length(declarator) -> int:
    if declarator is None:
        return 1
    multiplier = 1
    for node in _walk(declarator):
        if node.type == "array_declarator":
            length = 1
            for child in node.children:
                if child.type == "number_literal":
                    try:
                        length = int(_text(child), 0)
                    except ValueError:
                        length = 1
                    break
            multiplier *= max(1, length)
    return multiplier


def _bit_width(field_decl) -> int | None:
    clause = next((child for child in field_decl.children if child.type == "bitfield_clause"), None)
    if clause is None:
        return None
    for child in clause.children:
        if child.type == "number_literal":
            try:
                return int(_text(child), 0)
            except ValueError:
                return None
    return None


def _base_type_text(field_decl, declarator) -> str:
    if declarator is None:
        type_node = field_decl.child_by_field_name("type")
        return _normalise_type(_text(type_node) if type_node is not None else "")
    return _normalise_type(_text(field_decl)[: declarator.start_byte - field_decl.start_byte])


def _raw_field_type(base_type: str, declarator) -> str:
    stars = "*" * _pointer_depth(declarator)
    suffix = ""
    if _array_length(declarator) != 1:
        suffix = f"[{_array_length(declarator)}]"
    return f"{base_type} {stars}{suffix}".strip()


def _typedef_alias(struct_node) -> str | None:
    parent = getattr(struct_node, "parent", None)
    if parent is None or parent.type != "type_definition":
        return None
    identifiers = [child for child in parent.children if child.type == "type_identifier"]
    if not identifiers:
        return None
    return _text(identifiers[-1])


def _struct_name(struct_node) -> str:
    name_node = struct_node.child_by_field_name("name") or _named_child(struct_node, "type_identifier")
    if name_node is not None:
        return _text(name_node)
    alias = _typedef_alias(struct_node)
    return alias or "anonymous"


def _resolve_type(base_type: str, declarator, registry: dict[str, ResolvedType]) -> ResolvedType:
    platform_sizes = X86_64["type_sizes"]
    platform_alignments = X86_64["type_alignments"]

    if _pointer_depth(declarator) > 0:
        return ResolvedType(int(platform_sizes["pointer"]), int(platform_alignments["pointer"]))

    lookup = _normalise_type(base_type)
    if lookup.startswith("struct "):
        lookup_name = lookup.split(" ", 1)[1]
    elif lookup.startswith("class "):
        lookup_name = lookup.split(" ", 1)[1]
    else:
        lookup_name = lookup

    if lookup in platform_sizes:
        resolved = ResolvedType(int(platform_sizes[lookup]), int(platform_alignments[lookup]))
    elif lookup_name in registry:
        known = registry[lookup_name]
        resolved = ResolvedType(known.size, known.alignment)
    else:
        resolved = ResolvedType(0, 0, unresolved=True)

    length = _array_length(declarator)
    if length > 1 and not resolved.unresolved:
        return ResolvedType(resolved.size * length, resolved.alignment)
    return resolved


def _extract_fields(struct_node, registry: dict[str, ResolvedType]) -> list[dict]:
    body = struct_node.child_by_field_name("body") or _named_child(struct_node, "field_declaration_list")
    if body is None:
        return []

    fields: list[dict] = []
    for declaration in body.children:
        if declaration.type != "field_declaration":
            continue
        declarators = declaration.children_by_field_name("declarator")
        if not declarators:
            continue

        for declarator in declarators:
            if _is_function_member(declarator):
                continue
            name = _declarator_name(declarator)
            if not name:
                continue

            base_type = _base_type_text(declaration, declarator)
            resolved = _resolve_type(base_type, declarator, registry)
            raw_type = _raw_field_type(base_type, declarator)
            field = {
                "name": name,
                "raw_type": raw_type,
                "type": raw_type,
                "size": resolved.size,
                "alignment": resolved.alignment,
                "line": declaration.start_point[0] + 1,
            }
            width = _bit_width(declaration)
            if width is not None:
                field["bit_width"] = width
            if resolved.unresolved:
                field["unresolved"] = True
            fields.append(field)

    return fields


def parse_structs(source: str, language: str = "c") -> list[dict]:
    """Return C structs or C++ structs/classes with resolved x86_64 field sizes."""

    parser = _parser_for(language)
    tree = parser.parse(source.encode("utf-8"))
    registry: dict[str, ResolvedType] = {}
    result: list[dict] = []

    node_types = {"struct_specifier"}
    if language == "cpp":
        node_types.add("class_specifier")

    for node in _walk(tree.root_node):
        if node.type not in node_types:
            continue
        body = node.child_by_field_name("body") or _named_child(node, "field_declaration_list")
        if body is None:
            continue

        name = _struct_name(node)
        fields = _extract_fields(node, registry)
        if not fields:
            continue

        layout = compute_layout(fields, X86_64)
        resolved = ResolvedType(layout["total_size"], layout["alignment"])
        registry[name] = resolved
        alias = _typedef_alias(node)
        if alias:
            registry[alias] = resolved

        result.append(
            {
                "name": name,
                "fields": fields,
                "line": node.start_point[0] + 1,
            }
        )

    return result


if __name__ == "__main__":
    import json
    import sys

    lang = sys.argv[1] if len(sys.argv) > 1 else "c"
    print(json.dumps(parse_structs(sys.stdin.read(), lang), indent=2))
