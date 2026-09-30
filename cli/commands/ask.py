"""`nerve ask "<question>"` — ask the system a question (spec §47).

Posts to the canonical context-ask path ``POST /api/context/ask``. Note: the
current backend exposes only read-only §46 routers; the POST target is the
canonical contract path (see ``cli/CONTRACT_GAP_NOTES.md``).
"""
from __future__ import annotations

import click

from .._helpers import command_options, run_command


@click.command("ask")
@click.argument("question")
@command_options
@click.pass_context
def ask(ctx: click.Context, question: str, api_url: str, as_json: bool, output_format: str) -> None:
    """Ask a question to the system (POST /api/context/ask)."""
    run_command(
        ctx,
        "POST",
        "/api/context/ask",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
        json_body={"question": question},
    )
