"""Field reorder helpers."""

from __future__ import annotations

from layout_engine import compute_optimal_order


def suggest_order(fields: list[dict]) -> list[dict]:
    """Return fields sorted by decreasing alignment and size."""

    return compute_optimal_order(fields)
