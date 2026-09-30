"""`nerve task list | task show <id>` — task operations (spec §47)."""
from __future__ import annotations

import click

from .._helpers import command_options, run_command


@click.group("task")
def task() -> None:
    """Task operations (GET /api/tasks)."""


@task.command("list")
@command_options
@click.pass_context
def task_list(ctx: click.Context, api_url: str, as_json: bool, output_format: str) -> None:
    """List all tasks (GET /api/tasks)."""
    run_command(
        ctx,
        "GET",
        "/api/tasks",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
    )


@task.command("show")
@click.argument("task_id")
@command_options
@click.pass_context
def task_show(
    ctx: click.Context,
    task_id: str,
    api_url: str,
    as_json: bool,
    output_format: str,
) -> None:
    """Show a single task (GET /api/tasks/<id>)."""
    run_command(
        ctx,
        "GET",
        f"/api/tasks/{task_id}",
        api_url=api_url,
        as_json=as_json,
        output_format=output_format,
    )
