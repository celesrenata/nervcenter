"""`nerve changes [<name>] [--since 4h]` — recent changes (spec §47).

GET /api/changes. The optional entity name and ``--since`` window are sent as
query parameters (the current backend ignores them — see
``cli/CONTRACT_GAP_NOTES.md``) and ``--since`` also filters client-side when
items carry a machine-readable timestamp.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import click

from .._helpers import command_options, unwrap_envelope, validate_api_url
from ..client import ApiError, UnreachableError, resolve_base_url
from ..client import request as http_request
from ..output import OutputFormatter

EXIT_OK = 0
EXIT_UNREACHABLE = 127
EXIT_CONTRACT = 2

_SINCE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(s|m|h|d|w)\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_since(value: str) -> timedelta:
    """Parse human durations like ``4h``, ``30m``, ``2w`` into a timedelta."""
    match = _SINCE_RE.match(value)
    if not match:
        raise click.BadParameter(f"invalid --since {value!r} (expected e.g. 4h, 30m, 2d)")
    amount = float(match.group(1))
    unit = match.group(2).lower()
    return timedelta(seconds=amount * _UNIT_SECONDS[unit])


def _ts_value(item: dict) -> datetime | None:
    for key in ("timestamp", "created_at", "changed_at", "occurred_at"):
        raw = item.get(key)
        if isinstance(raw, str):
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
    return None


@click.command("changes")
@click.argument("name", required=False)
@click.option(
    "--since",
    "since",
    default=None,
    help="Only show changes from the last <duration> (e.g. 4h, 30m, 2d)",
)
@command_options
@click.pass_context
def changes(
    ctx: click.Context,
    name: str | None,
    since: str | None,
    api_url: str,
    as_json: bool,
    output_format: str,
) -> None:
    """Show recent changes, optionally for one entity (GET /api/changes)."""
    base_url = resolve_base_url(api_url)
    validate_api_url(base_url)
    params: dict[str, str] = {}
    if name:
        params["entity"] = name
    if since:
        params["since"] = since

    try:
        response = http_request("GET", base_url, "/api/changes", params=params or None)
    except UnreachableError as exc:
        click.echo(f"error: {exc}", err=True)
        ctx.exit(EXIT_UNREACHABLE)
        return
    except ApiError as exc:
        click.echo(f"error: {exc}", err=True)
        ctx.exit(EXIT_CONTRACT)
        return

    items = unwrap_envelope(response.data) or []
    if since:
        cutoff = datetime.now(UTC) - parse_since(since)
        kept = []
        for item in items:
            if not isinstance(item, dict):
                kept.append(item)
                continue
            ts = _ts_value(item)
            if ts is None or ts >= cutoff:
                kept.append(item)
        items = kept

    if as_json:
        click.echo(OutputFormatter.format_json(items))
    else:
        click.echo(OutputFormatter.render(items, output_format))
    ctx.exit(EXIT_OK)
