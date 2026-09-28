import click

@click.command()
def status():
    """Show system status"""
    click.echo("System status: Operational")