"""`nerve status` — system health and API version (spec §47)."""
from __future__ import annotations

import click

from .._helpers import command_options, validate_api_url
from ..client import ApiError, UnreachableError, resolve_base_url
from ..client import request as http_request
from ..output import OutputFormatter

EXIT_OK = 0
EXIT_UNREACHABLE = 127
EXIT_CONTRACT = 2


@click.command("status")
@command_options
@click.pass_context
def status(ctx: click.Context, api_url: str, as_json: bool, output_format: str) -> None:
    """Show system status (GET /api/health + GET /version)."""
    base_url = resolve_base_url(api_url)
    validate_api_url(base_url)
    try:
        health = http_request("GET", base_url, "/api/health").data
        version = http_request("GET", base_url, "/version").data
    except UnreachableError as exc:
        click.echo(f"error: {exc}", err=True)
        ctx.exit(EXIT_UNREACHABLE)
        return
    except ApiError as exc:
        click.echo(f"error: {exc}", err=True)
        ctx.exit(EXIT_CONTRACT)
        return

    payload = {"api": base_url, "health": health, "version": version}
    if as_json:
        click.echo(OutputFormatter.format_json(payload))
        ctx.exit(EXIT_OK)
        return

    checks = health.get("checks", {}) if isinstance(health, dict) else {}
    lines = [
        f"api:    {base_url}",
        f"status: {health.get('status', 'unknown') if isinstance(health, dict) else 'unknown'}",
        f"version: {health.get('version', 'unknown') if isinstance(health, dict) else 'unknown'}",
    ]
    if isinstance(version, dict) and version.get("version"):
        lines.append(f"api-version: {version['version']}")
    for name, check in checks.items():
        if isinstance(check, dict):
            detail = check.get("message") or check.get("status") or ""
            lines.append(f"check {name}: {check.get('status', '?')} {detail}".rstrip())
    click.echo("\n".join(lines))
    ctx.exit(EXIT_OK)
