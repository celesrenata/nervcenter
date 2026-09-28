import click

@click.command()
@click.argument('incident_id', type=str)
def incident(incident_id):
    """Show information about an incident"""
    click.echo(f"Incident ID: {incident_id}")
    # Here you would implement the actual incident lookup logic
    click.echo("Incident details: [Implementation pending]")