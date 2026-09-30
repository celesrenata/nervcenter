"""`nerve routes` — inference routes (spec §47)."""
from __future__ import annotations

import click

from .._helpers import command_options, run_command


@click.command("routes")
@command_options
@click.pass_context
def routes(ctx: click.Context, api_url: str, as_json: bool, output_format: str) -> None:
    """List inference routes (GET /api/routes)."""
    run_command(
        ctx,
        "GET",
        "/api/routes",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
    )
