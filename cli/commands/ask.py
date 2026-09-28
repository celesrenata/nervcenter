import click

@click.command()
@click.argument('question', type=str)
def ask(question):
    """Ask a question to the system"""
    click.echo(f"You asked: {question}")
    # Here you would implement the actual question-answering logic
    click.echo("Answer: [Implementation pending]")