class Documentation:
    @staticmethod
    def get_help(command):
        """Get help for a specific command"""
        help_text = {
            "status": "Show system status",
            "ask": "Ask a question to the system",
            "entity": "Show information about an entity",
            "changes": "Show planned changes",
            "goal": "Show information about a goal",
            "task": "Show information about a task",
            "agents": "Show information about agents",
            "compute": "Show compute resources",
            "routes": "Show routes",
            "incident": "Show information about an incident"
        }
        return help_text.get(command, "No help available for this command")

    @staticmethod
    def get_all_commands():
        """Get a list of all available commands"""
        return [
            "status",
            "ask",
            "entity",
            "changes",
            "goal",
            "task",
            "agents",
            "compute",
            "routes",
            "incident"
        ]

    @staticmethod
    def add_help_to_command(command):
        """Add help to a command"""
        command.help = Documentation.get_help(command.name)

    @staticmethod
    def add_help_to_all_commands(commands):
        """Add help to all commands"""
        for command in commands:
            Documentation.add_help_to_command(command)