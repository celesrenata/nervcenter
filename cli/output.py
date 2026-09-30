"""Output formatting for the NerveCenter CLI.

Zero new dependencies: ``tabulate`` is used opportunistically when installed,
otherwise a minimal built-in table formatter renders the same grid output.
"""
from __future__ import annotations

import json
from typing import Any

Row = list[Any]
Table = tuple[list[str], list[Row]]

try:  # pragma: no cover - exercised only when tabulate is installed
    from tabulate import tabulate as _tabulate
except ImportError:  # pragma: no cover
    _tabulate = None


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value)


def _minimal_table(headers: list[str], rows: list[Row]) -> str:
    """Render a simple aligned table with no external dependencies."""
    cols = len(headers)
    table_rows = [[_cell(v) for v in row] + [""] * (cols - len(row)) for row in rows]
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in table_rows)) if table_rows else len(headers[i])
        for i in range(cols)
    ]
    sep = "-+-".join("-" * w for w in widths)
    out = [
        " | ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True)),
        sep,
    ]
    out.extend(
        " | ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)) for r in table_rows
    )
    return "\n".join(out)


def minimal_table(data: Table) -> str:
    """Public wrapper around the built-in table formatter."""
    return _minimal_table(*data)


def table_to_text(data: Table) -> str:
    """Render a table with ``tabulate`` when available, else built-in."""
    headers, rows = data
    if _tabulate is not None:  # type: ignore[union-attr]
        return _tabulate(rows, headers=headers, tablefmt="grid")
    return _minimal_table(headers, rows)


def infer_table(data: Any) -> Table | None:
    """Infer (headers, rows) from a list of homogeneous dicts, else None."""
    if not isinstance(data, list) or not data:
        return None
    items = [row for row in data if isinstance(row, dict)]
    if len(items) != len(data):
        return None
    headers: list[str] = []
    for row in items:
        for key in row:
            if key not in headers:
                headers.append(str(key))
    rows = [[row.get(h) for h in headers] for row in items]
    return headers, rows


def format_json(data: Any) -> str:
    """Format data as pretty-printed JSON."""
    return json.dumps(data, indent=2, default=str)


def format_value(data: Any) -> str:
    """Human-readable text for a single (non-list) value."""
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{key}:\n{json.dumps(value, indent=2, default=str)}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)
    if data is None:
        return "(empty)"
    return str(data)


class OutputFormatter:
    """Formats CLI payloads as JSON, table, or text."""

    @staticmethod
    def format_json(data: Any) -> str:  # noqa: D401 - parity with skeleton API
        return format_json(data)

    @staticmethod
    def format_table(data: Table) -> str:
        return table_to_text(data)

    @staticmethod
    def format_text(data: Any) -> str:
        if isinstance(data, list):
            inferred = infer_table(data)
            if inferred is not None:
                return table_to_text(inferred)
            if not data:
                return "(empty)"
            return "\n".join(format_value(item) for item in data)
        return format_value(data)

    @classmethod
    def render(cls, data: Any, fmt: str) -> str:
        """Format ``data`` according to ``fmt`` (json | table | text)."""
        if fmt == "json":
            return cls.format_json(data)
        if fmt == "table":
            inferred = infer_table(data)
            if inferred is not None:
                return cls.format_table(inferred)
            return cls.format_text(data)
        return cls.format_text(data)
