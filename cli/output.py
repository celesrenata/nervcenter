import json
from tabulate import tabulate

class OutputFormatter:
    @staticmethod
    def format_json(data):
        """Format data as JSON"""
        return json.dumps(data, indent=2)

    @staticmethod
    def format_table(data, headers=None):
        """Format data as a table"""
        if headers:
            return tabulate(data, headers=headers, tablefmt="grid")
        return tabulate(data, tablefmt="grid")

    @staticmethod
    def format_text(data):
        """Format data as plain text"""
        if isinstance(data, dict):
            return "\n".join(f"{k}: {v}" for k, v in data.items())
        elif isinstance(data, list):
            return "\n".join(str(item) for item in data)
        return str(data)

    @staticmethod
    def format_output(data, output_format):
        """Format data based on the specified output format"""
        if output_format == 'json':
            return OutputFormatter.format_json(data)
        elif output_format == 'table':
            return OutputFormatter.format_table(data)
        else:
            return OutputFormatter.format_text(data)