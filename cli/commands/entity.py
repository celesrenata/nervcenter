"""`nerve entity <name>` — show an entity (spec §47).

Lookup order: ``GET /api/entities/<id>`` by ID; on 404 fall back to
``GET /api/entities`` and match ``name`` (the list endpoint has no query
parameter in the current backend — see ``cli/CONTRACT_GAP_NOTES.md``).
"""
from __future__ import annotations

import click

from .._helpers import command_options, unwrap_envelope, validate_api_url
from ..client import ApiError, UnreachableError, resolve_base_url
from ..client import request as http_request
from ..output import OutputFormatter

EXIT_OK = 0
EXIT_UNREACHABLE = 127
EXIT_CONTRACT = 2


@click.command("entity")
@click.argument("name")
@command_options
@click.pass_context
def entity(ctx: click.Context, name: str, api_url: str, as_json: bool, output_format: str) -> None:
    """Show information about an entity (GET /api/entities/<id> | /api/entities)."""
    base_url = resolve_base_url(api_url)
    validate_api_url(base_url)
    try:
        try:
            response = http_request("GET", base_url, f"/api/entities/{name}")
            found = response.data
            matched_by = "id"
        except ApiError as exc:
            if exc.status != 404:
                raise
            listing = unwrap_envelope(http_request("GET", base_url, "/api/entities").data)
            found = None
            matched_by = "name"
            for item in listing or []:
                if isinstance(item, dict) and item.get("name") == name:
                    found = item
                    break
            if found is None:
                click.echo(f"error: entity {name!r} not found", err=True)
                ctx.exit(EXIT_CONTRACT)
                return
    except UnreachableError as exc:
        click.echo(f"error: {exc}", err=True)
        ctx.exit(EXIT_UNREACHABLE)
        return
    except ApiError as exc:
        click.echo(f"error: {exc}", err=True)
        ctx.exit(EXIT_CONTRACT)
        return

    payload = {"match": matched_by, "entity": found}
    if as_json:
        click.echo(OutputFormatter.format_json(payload))
        ctx.exit(EXIT_OK)
        return
    click.echo(OutputFormatter.render(found, output_format))
    ctx.exit(EXIT_OK)
