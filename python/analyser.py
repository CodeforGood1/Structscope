"""Padding, cache-line, and reorder analysis for layout results."""

from __future__ import annotations

from layout_engine import compute_layout
from platforms import get_platform
from suggester import suggest_order


def analyse(layout_result: dict, platform_name: str, cache_line_size: int = 64) -> dict:
    platform = get_platform(platform_name)
    total_size = int(layout_result.get("total_size") or 0)
    waste_bytes = int(layout_result.get("total_padding") or 0)
    waste_ratio = (waste_bytes / total_size) if total_size else 0.0

    fields = list(layout_result.get("fields") or [])
    optimal_order = suggest_order(fields)
    optimal_layout = compute_layout(optimal_order, platform)
    optimal_size = int(optimal_layout["total_size"])
    savings = max(0, total_size - optimal_size)

    splits = []
    warnings = []
    if waste_bytes > 0:
        warnings.append(f"{waste_bytes} bytes wasted ({waste_ratio * 100:.1f}%)")

    line_size = max(1, int(cache_line_size or 64))
    for field in fields:
        size = int(field.get("size") or 0)
        if size <= 0:
            continue
        offset = int(field.get("offset") or 0)
        if offset // line_size != (offset + size - 1) // line_size:
            name = str(field.get("name", ""))
            splits.append(
                {
                    "field_name": name,
                    "offset": offset,
                    "size": size,
                    "line_size": line_size,
                }
            )
            warnings.append(f"Field {name} straddles cache line boundary")

    return {
        "waste_bytes": waste_bytes,
        "waste_ratio": waste_ratio,
        "optimal_size": optimal_size,
        "savings": savings,
        "cache_line_splits": splits,
        "warnings": warnings,
        "optimal_order": optimal_order,
    }
