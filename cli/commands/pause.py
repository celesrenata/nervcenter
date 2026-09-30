"""`nerve pause-agents` — emergency pause of all agents (spec §47)."""
from __future__ import annotations

import click

from .._helpers import command_options, run_command


@click.command("pause-agents")
@command_options
@click.pass_context
def pause_agents(ctx: click.Context, api_url: str, as_json: bool, output_format: str) -> None:
    """Pause all running agents (POST /api/agents/pause).

    Note: the backend does not currently expose this POST path; the command
    targets the canonical contract path and reports the contract error
    (exit 2) until the backend implements it. See CONTRACT_GAP_NOTES.md.
    """
    run_command(
        ctx,
        "POST",
        "/api/agents/pause",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
        json_body={},
    )
