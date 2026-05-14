"""Newline-delimited JSON-RPC server for StructScope."""

from __future__ import annotations

import json
import re
import sys
import traceback
from typing import Any

from analyser import analyse
from layout_engine import compute_layout
from parser_c import parse_structs
from parser_rust import parse_structs_rust
from platforms import PLATFORMS, detect_host_platform, detect_host_platform_info, get_platform


RUST_FIXED = {
    "bool": (1, 1),
    "i8": (1, 1),
    "u8": (1, 1),
    "i16": (2, 2),
    "u16": (2, 2),
    "i32": (4, 4),
    "u32": (4, 4),
    "f32": (4, 4),
    "i64": (8, 8),
    "u64": (8, 8),
    "f64": (8, 8),
}
QUALIFIERS = {
    "const",
    "volatile",
    "restrict",
    "__restrict",
    "__restrict__",
    "mutable",
    "static",
    "register",
}


def _normalise_type(raw_type: str) -> str:
    collapsed = " ".join(str(raw_type).replace("\n", " ").replace("\t", " ").split())
    tokens = [token for token in collapsed.split(" ") if token not in QUALIFIERS]
    return " ".join(tokens).strip()


def _split_array(raw_type: str) -> tuple[str, int]:
    text = _normalise_type(raw_type)
    multiplier = 1
    while True:
        match = re.search(r"\[(\d+)\]\s*$", text)
        if not match:
            return text, multiplier
        multiplier *= max(1, int(match.group(1)))
        text = text[: match.start()].strip()


def _resolve_c(raw_type: str, platform: dict, registry: dict[str, dict[str, int]]) -> tuple[int, int, bool]:
    base, array_len = _split_array(raw_type)
    sizes = platform["type_sizes"]
    alignments = platform["type_alignments"]

    if "*" in base:
        return int(sizes["pointer"]) * array_len, int(alignments["pointer"]), False

    lookup = _normalise_type(base)
    if lookup.startswith("struct "):
        lookup_name = lookup.split(" ", 1)[1]
    elif lookup.startswith("class "):
        lookup_name = lookup.split(" ", 1)[1]
    else:
        lookup_name = lookup

    if lookup in sizes:
        return int(sizes[lookup]) * array_len, int(alignments[lookup]), False
    if lookup_name in registry:
        known = registry[lookup_name]
        return int(known["size"]) * array_len, int(known["alignment"]), False
    return 0, 0, True


def _resolve_rust(raw_type: str, platform: dict, registry: dict[str, dict[str, int]]) -> tuple[int, int, bool]:
    raw = _normalise_type(raw_type)
    sizes = platform["type_sizes"]
    alignments = platform["type_alignments"]

    if raw.startswith("&") or raw.startswith("*"):
        return int(sizes["pointer"]), int(alignments["pointer"]), False
    if raw in {"usize", "isize"}:
        return int(sizes["pointer"]), int(alignments["pointer"]), False
    if raw in RUST_FIXED:
        return RUST_FIXED[raw][0], RUST_FIXED[raw][1], False
    if raw in registry:
        known = registry[raw]
        return int(known["size"]), int(known["alignment"]), False
    return 0, 0, True


def _retarget_structs(structs: list[dict], platform: dict, language: str) -> list[dict]:
    registry: dict[str, dict[str, int]] = {}
    retargeted = []

    for struct in structs:
        fields = []
        for field in struct.get("fields", []):
            raw_type = str(field.get("raw_type") or field.get("type") or "")
            if language == "rust":
                size, alignment, unresolved = _resolve_rust(raw_type, platform, registry)
            else:
                size, alignment, unresolved = _resolve_c(raw_type, platform, registry)

            adjusted = dict(field)
            adjusted["size"] = size
            adjusted["alignment"] = alignment
            if unresolved:
                adjusted["unresolved"] = True
            else:
                adjusted.pop("unresolved", None)
            fields.append(adjusted)

        layout = compute_layout(fields, platform)
        registry[str(struct.get("name", ""))] = {
            "size": int(layout["total_size"]),
            "alignment": int(layout["alignment"]),
        }
        retargeted.append({**struct, "fields": fields, "layout": layout})

    return retargeted


def analyse_source(source: str, language: str, platform_name: str = "x86_64", cache_line: int = 64) -> dict[str, Any]:
    requested_platform = platform_name or "x86_64"
    actual_platform = detect_host_platform() if requested_platform == "auto" else requested_platform
    platform = get_platform(actual_platform)

    if language in {"c", "cpp"}:
        parsed = parse_structs(source, language)
    elif language == "rust":
        parsed = parse_structs_rust(source)
    else:
        raise ValueError("language must be one of: c, cpp, rust")

    retargeted = _retarget_structs(parsed, platform, language)
    response_structs = []
    for struct in retargeted:
        layout = struct["layout"]
        response_structs.append(
            {
                "name": struct.get("name"),
                "line": struct.get("line"),
                "fields": struct.get("fields", []),
                "layout": layout,
                "analysis": analyse(layout, actual_platform, cache_line),
            }
        )
    return {
        "structs": response_structs,
        "platform": actual_platform,
        "requested_platform": requested_platform,
        "cache_line": cache_line,
    }


def _analyse_request(payload: dict[str, Any]) -> dict[str, Any]:
    source = str(payload.get("source") or "")
    language = str(payload.get("language") or "c")
    platform_name = str(payload.get("platform") or "x86_64")
    cache_line = int(payload.get("cache_line") or 64)
    return analyse_source(source, language, platform_name, cache_line)


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    method = request.get("method")
    if method == "ping":
        return {"pong": True}
    if method == "platforms":
        return {"platforms": list(PLATFORMS.keys())}
    if method == "detect_platform":
        return detect_host_platform_info()
    if method == "analyse":
        return _analyse_request(request)
    raise ValueError(f"Unknown method: {method}")


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
        except Exception as exc:  # Keep the server alive on malformed requests.
            if "--debug" in sys.argv:
                traceback.print_exc(file=sys.stderr)
            response = {"error": str(exc)}
        sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
