import click

@click.command()
@click.argument('goal_id', type=str)
def goal(goal_id):
    """Show information about a goal"""
    click.echo(f"Goal ID: {goal_id}")
    # Here you would implement the actual goal lookup logic
    click.echo("Goal details: [Implementation pending]")