"""Command-line entry point for StructScope analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from server import analyse_source


EXTENSION_LANGUAGE = {
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".rs": "rust",
}


def infer_language(path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    try:
        return EXTENSION_LANGUAGE[path.suffix.lower()]
    except KeyError as exc:
        raise SystemExit(f"Cannot infer language from '{path.name}'. Use --language c|cpp|rust.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze C, C++, or Rust struct layout locally.")
    parser.add_argument("file", type=Path, help="Source file to analyze")
    parser.add_argument("--language", choices=["c", "cpp", "rust"], help="Override language detection")
    parser.add_argument("--platform", default="auto", help="ABI platform: auto, x86_64, arm64, arm32, avr, riscv32")
    parser.add_argument("--cache-line", type=int, default=64, help="Cache-line size in bytes")
    parser.add_argument("--struct", dest="struct_name", help="Print only one struct by name")
    parser.add_argument("--json", action="store_true", help="Emit full JSON instead of a compact table")
    return parser


def print_table(result: dict, struct_name: str | None) -> None:
    structs = result.get("structs", [])
    if struct_name:
        structs = [item for item in structs if item.get("name") == struct_name]
    if not structs:
        raise SystemExit("No matching structs found.")

    print(f"StructScope CLI | platform={result.get('platform')} cache_line={result.get('cache_line')}B")
    for struct in structs:
        layout = struct["layout"]
        analysis = struct["analysis"]
        print()
        print(
            f"{struct['name']}: total={layout['total_size']}B "
            f"padding={analysis['waste_bytes']}B ({analysis['waste_ratio'] * 100:.1f}%) "
            f"optimal={analysis['optimal_size']}B savings={analysis['savings']}B"
        )
        print("  field                 type                  off   size  pad")
        print("  -------------------------------------------------------------")
        for field in layout["fields"]:
            print(
                f"  {field['name'][:21]:21} "
                f"{(field.get('raw_type') or field.get('type') or '')[:21]:21} "
                f"{field['offset']:>4}  {field['size']:>4}  {field.get('padding_after', 0):>3}"
            )
        for warning in analysis.get("warnings", []):
            print(f"  warning: {warning}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_path = args.file
    source = source_path.read_text(encoding="utf-8")
    language = infer_language(source_path, args.language)
    result = analyse_source(source, language, args.platform, args.cache_line)
    if args.json:
        if args.struct_name:
            result = {
                **result,
                "structs": [item for item in result.get("structs", []) if item.get("name") == args.struct_name],
            }
        json.dump(result, sys.stdout, indent=2)
        print()
    else:
        print_table(result, args.struct_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

