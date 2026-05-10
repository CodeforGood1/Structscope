"""Platform ABI tables used by StructScope's static layout engine."""

from __future__ import annotations

from copy import deepcopy


def _with_aliases(type_sizes: dict[str, int], type_alignments: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    aliases = {
        "signed char": "char",
        "unsigned char": "char",
        "bool": "char",
        "_Bool": "char",
        "signed short": "short",
        "unsigned short": "short",
        "short int": "short",
        "signed short int": "short",
        "unsigned short int": "short",
        "signed int": "int",
        "unsigned int": "int",
        "unsigned": "int",
        "signed": "int",
        "signed long": "long",
        "unsigned long": "long",
        "long int": "long",
        "signed long int": "long",
        "unsigned long int": "long",
        "signed long long": "long long",
        "unsigned long long": "long long",
        "long long int": "long long",
        "signed long long int": "long long",
        "unsigned long long int": "long long",
        "size_t": "pointer",
        "intptr_t": "pointer",
        "uintptr_t": "pointer",
    }
    for alias, target in aliases.items():
        type_sizes[alias] = type_sizes[target]
        type_alignments[alias] = type_alignments[target]
    return type_sizes, type_alignments


def _platform(pointer_size: int, max_align: int, sizes: dict[str, int], alignments: dict[str, int]) -> dict[str, object]:
    type_sizes, type_alignments = _with_aliases(dict(sizes), dict(alignments))
    return {
        "pointer_size": pointer_size,
        "max_align": max_align,
        "type_sizes": type_sizes,
        "type_alignments": type_alignments,
    }


PLATFORMS: dict[str, dict[str, object]] = {
    "x86_64": _platform(
        pointer_size=8,
        max_align=8,
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 8,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 8,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
    ),
    "arm64": _platform(
        pointer_size=8,
        max_align=8,
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 8,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 8,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 8,
        },
    ),
    "arm32": _platform(
        pointer_size=4,
        max_align=8,
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 4,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 4,
        },
    ),
    "avr": _platform(
        pointer_size=2,
        max_align=1,
        sizes={
            "char": 1,
            "short": 2,
            "int": 2,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 4,
            "pointer": 2,
        },
        alignments={
            "char": 1,
            "short": 1,
            "int": 1,
            "long": 1,
            "long long": 1,
            "float": 1,
            "double": 1,
            "pointer": 1,
        },
    ),
    "riscv32": _platform(
        pointer_size=4,
        max_align=8,
        sizes={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 4,
        },
        alignments={
            "char": 1,
            "short": 2,
            "int": 4,
            "long": 4,
            "long long": 8,
            "float": 4,
            "double": 8,
            "pointer": 4,
        },
    ),
}


def get_platform(name: str) -> dict[str, object]:
    """Return a defensive copy of an ABI table by name."""

    try:
        return deepcopy(PLATFORMS[name])
    except KeyError as exc:
        known = ", ".join(sorted(PLATFORMS))
        raise ValueError(f"Unknown platform '{name}'. Known platforms: {known}") from exc
