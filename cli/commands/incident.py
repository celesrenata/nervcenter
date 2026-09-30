"""`nerve incident investigate <name> | incident show <id>` (spec §47)."""
from __future__ import annotations

import click

from .._helpers import command_options, run_command


@click.group("incident")
def incident() -> None:
    """Incident operations (GET /api/incidents)."""


@incident.command("investigate")
@click.argument("name")
@command_options
@click.pass_context
def investigate(
    ctx: click.Context,
    name: str,
    api_url: str,
    as_json: bool,
    output_format: str,
) -> None:
    """Start an investigation for an entity (POST /api/incidents/investigate).

    Note: the backend does not currently expose this POST path; the command
    targets the canonical contract path and reports the contract error
    (exit 2) until the backend implements it. See CONTRACT_GAP_NOTES.md.
    """
    run_command(
        ctx,
        "POST",
        "/api/incidents/investigate",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
        json_body={"entity": name},
    )


@incident.command("show")
@click.argument("incident_id")
@command_options
@click.pass_context
def show(
    ctx: click.Context,
    incident_id: str,
    api_url: str,
    as_json: bool,
    output_format: str,
) -> None:
    """Show a single incident (GET /api/incidents/<id>)."""
    run_command(
        ctx,
        "GET",
        f"/api/incidents/{incident_id}",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
    )
