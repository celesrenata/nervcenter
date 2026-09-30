"""`nerve goal list | goal show <id>` — goal operations (spec §47)."""
from __future__ import annotations

import click

from .._helpers import command_options, run_command


@click.group("goal")
def goal() -> None:
    """Goal operations (GET /api/goals)."""


@goal.command("list")
@command_options
@click.pass_context
def goal_list(ctx: click.Context, api_url: str, as_json: bool, output_format: str) -> None:
    """List all goals (GET /api/goals)."""
    run_command(
        ctx,
        "GET",
        "/api/goals",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
    )


@goal.command("show")
@click.argument("goal_id")
@command_options
@click.pass_context
def goal_show(
    ctx: click.Context,
    goal_id: str,
    api_url: str,
    as_json: bool,
    output_format: str,
) -> None:
    """Show a single goal (GET /api/goals/<id>)."""
    run_command(
        ctx,
        "GET",
        f"/api/goals/{goal_id}",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
    )
