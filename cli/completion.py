import click
from .docs import Documentation

class CommandCompletion:
    @staticmethod
    def get_completion(ctx, args, incomplete):
        """Get command completion suggestions"""
        commands = Documentation.get_all_commands()
        return [cmd for cmd in commands if cmd.startswith(incomplete)]

    @staticmethod
    def register_completion(cli):
        """Register command completion for the CLI"""
        for cmd in cli.commands.values():
            cmd.shell_complete = CommandCompletion.get_completion