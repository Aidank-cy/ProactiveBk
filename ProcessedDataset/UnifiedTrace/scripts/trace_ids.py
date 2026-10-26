"""Stable trace IDs in the chosen filtered input's deterministic row order."""

PREFIXES = {
    "wildchat_1m": "WildChat_1M",
    "wildchat_4_8m": "WildChat_4_8M",
    "swe_chat": "SWE_Chat",
}


ID_WIDTH = 7  # Supports the 4.8M WildChat source without changing width.


def trace_id(source: str, zero_based_row_index: int) -> str:
    if zero_based_row_index < 0:
        raise ValueError("row index must be nonnegative")
    if zero_based_row_index + 1 >= 10 ** ID_WIDTH:
        raise ValueError("trace ordinal exceeds the configured seven-digit ID space")
    return f"{PREFIXES[source]}_{zero_based_row_index + 1:0{ID_WIDTH}d}"
