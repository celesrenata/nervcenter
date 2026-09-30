"""`nerve agents` — list agents (spec §47)."""
from __future__ import annotations

import click

from .._helpers import command_options, run_command


@click.command("agents")
@command_options
@click.pass_context
def agents(ctx: click.Context, api_url: str, as_json: bool, output_format: str) -> None:
    """List registered agents (GET /api/agents)."""
    run_command(
        ctx,
        "GET",
        "/api/agents",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
    )
