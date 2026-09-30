"""Stdio entrypoint for the NerveCenter MCP server (``python -m mcp``).

Reads one JSON-RPC 2.0 message per line from stdin and writes one JSON-RPC
response line to stdout. Notifications (no ``id``) produce no line, per the
JSON-RPC 2.0 spec; malformed lines produce a ``PARSE_ERROR`` envelope.

Tool calls proxy to the §46 NerveCenter HTTP API: the base URL comes from the
``NERVE_API`` environment variable (default ``http://localhost:8000``).
"""

from __future__ import annotations

import json
import sys

from mcp.core import build_registry, handle_message
from mcp.protocol import PARSE_ERROR, make_error


def main() -> int:
    """Run the stdio JSON-RPC loop until stdin is closed."""
    registry = build_registry()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            sys.stdout.write(json.dumps(make_error(None, PARSE_ERROR, "parse error")) + "\n")
            sys.stdout.flush()
            continue
        response = handle_message(message, registry, None)
        if response is None:  # notification: no response
            continue
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
