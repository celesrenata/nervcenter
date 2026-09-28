import click
from .output import OutputFormatter
from .docs import Documentation

@click.group()
@click.version_option()
@click.option('--output-format', default='text', type=click.Choice(['text', 'json', 'table']), help='Output format')
@click.pass_context
def cli(ctx, output_format):
    """NerveCenter Command Line Interface"""
    ctx.obj = {'output_format': output_format}

# Import all commands
from .commands import *

if __name__ == '__main__':
    from .completion import CommandCompletion
    CommandCompletion.register_completion(cli)
    cli()