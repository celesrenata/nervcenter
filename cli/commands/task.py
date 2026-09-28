import click

@click.command()
@click.argument('task_id', type=str)
def task(task_id):
    """Show information about a task"""
    click.echo(f"Task ID: {task_id}")
    # Here you would implement the actual task lookup logic
    click.echo("Task details: [Implementation pending]")