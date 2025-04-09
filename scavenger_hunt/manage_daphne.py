#!/usr/bin/env python
"""Django's command-line utility for running Daphne ASGI server."""
import os
import sys


def main():
    """Run administrative tasks with Daphne ASGI server."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scavenger_hunt.settings')
    try:
        from django.core.management import execute_from_command_line
        from django.core.management.commands.runserver import Command as runserver
        from daphne.cli import CommandLineInterface
        
        # Override default server with Daphne
        runserver.server_cls = 'daphne.server.Server'
        
        # Set up Daphne CLI
        if sys.argv[1] == 'runserver':
            sys.argv[1] = 'daphne'
            sys.argv.append('scavenger_hunt.asgi:application')
            cli = CommandLineInterface()
            cli.run(sys.argv[1:])
        else:
            execute_from_command_line(sys.argv)
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc


if __name__ == '__main__':
    main() 