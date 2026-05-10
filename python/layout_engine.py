"""C-like ABI struct layout computation."""

from __future__ import annotations

from copy import deepcopy


def _align_up(offset: int, alignment: int) -> int:
    if alignment <= 1:
        return offset
    return ((offset + alignment - 1) // alignment) * alignment


def _field_alignment(field: dict, platform: dict) -> int:
    max_align = int(platform.get("max_align", 1))
    alignment = int(field.get("alignment") or 1)
    return max(1, min(alignment, max_align))


def compute_layout(fields: list[dict], platform: dict) -> dict:
    """Compute offsets, padding, total size, and aggregate alignment for fields."""

    laid_out_fields: list[dict] = []
    offset = 0
    struct_alignment = 1
    total_padding = 0

    for index, field in enumerate(fields):
        alignment = _field_alignment(field, platform)
        size = max(0, int(field.get("size") or 0))
        struct_alignment = max(struct_alignment, alignment)

        aligned_offset = _align_up(offset, alignment)
        total_padding += aligned_offset - offset

        laid_out = deepcopy(field)
        laid_out["offset"] = aligned_offset
        laid_out["size"] = size
        laid_out["alignment"] = alignment
        laid_out["padding_after"] = 0
        laid_out["index"] = index
        laid_out_fields.append(laid_out)

        offset = aligned_offset + size

    for current, nxt in zip(laid_out_fields, laid_out_fields[1:]):
        end = int(current["offset"]) + int(current["size"])
        current["padding_after"] = max(0, int(nxt["offset"]) - end)

    total_size = _align_up(offset, struct_alignment)
    total_padding += total_size - offset

    return {
        "fields": laid_out_fields,
        "total_size": total_size,
        "total_padding": total_padding,
        "alignment": struct_alignment,
    }


def compute_optimal_order(fields: list[dict]) -> list[dict]:
    """Return a greedy padding-minimising field order."""

    return sorted(
        (deepcopy(field) for field in fields),
        key=lambda field: (
            -int(field.get("alignment") or 0),
            -int(field.get("size") or 0),
        ),
    )
