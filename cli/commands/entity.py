import click

@click.command()
@click.argument('entity_id', type=str)
def entity(entity_id):
    """Show information about an entity"""
    click.echo(f"Entity ID: {entity_id}")
    # Here you would implement the actual entity lookup logic
    click.echo("Entity details: [Implementation pending]")