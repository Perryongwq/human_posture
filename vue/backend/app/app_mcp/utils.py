"""
MCP result helpers — transform raw MCP responses into frontend-friendly shapes.
"""
from typing import Any, Dict, List, Optional


def to_records(result: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert a raw MCP result into a list of dicts (array of objects).

    Transforms::

        {
          "data": {
            "columns": ["HID1000", "CDC0068", ...],
            "rows":    [["2025-11-17T09:55:41", 1, ...], ...]
          }
        }

    Into::

        [
          {"HID1000": "2025-11-17T09:55:41", "CDC0068": 1, ...},
          ...
        ]

    Returns an empty list if result is None or contains no rows.
    """
    if not result:
        return []

    data = result.get("data", result)  # handle both wrapped and unwrapped shapes
    columns: List[str] = data.get("columns", [])
    rows: List[list]   = data.get("rows", [])

    if not columns or not rows:
        return []

    return [dict(zip(columns, row)) for row in rows]
