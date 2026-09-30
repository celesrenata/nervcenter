"""`nerve compute` — compute resources (spec §47)."""
from __future__ import annotations

import click

from .._helpers import command_options, run_command


@click.command("compute")
@command_options
@click.pass_context
def compute(ctx: click.Context, api_url: str, as_json: bool, output_format: str) -> None:
    """List compute resources (GET /api/compute)."""
    run_command(
        ctx,
        "GET",
        "/api/compute",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
    )
