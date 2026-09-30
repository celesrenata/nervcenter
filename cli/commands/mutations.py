"""`nerve stop-mutations` — stop all mutation execution (spec §47)."""
from __future__ import annotations

import click

from .._helpers import command_options, run_command


@click.command("stop-mutations")
@command_options
@click.pass_context
def stop_mutations(ctx: click.Context, api_url: str, as_json: bool, output_format: str) -> None:
    """Stop all pending/in-flight mutations (POST /api/changes/stop-mutations).

    Note: the backend does not currently expose this POST path; the command
    targets the canonical contract path and reports the contract error
    (exit 2) until the backend implements it. See CONTRACT_GAP_NOTES.md.
    """
    run_command(
        ctx,
        "POST",
        "/api/changes/stop-mutations",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
        json_body={},
    )
