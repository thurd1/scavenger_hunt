#!/usr/bin/env python
import os
import sys
import subprocess

# Configuration
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 8000       # Default port

if __name__ == "__main__":
    print("Starting Daphne server...")
    
    # First, make sure to collect static files
    print("Collecting static files...")
    subprocess.run([sys.executable, "manage.py", "collectstatic", "--noinput"])
    
    # Run Daphne directly with command line args
    # This approach avoids all the import and app registry issues
    cmd = [
        sys.executable, 
        "-m", "daphne", 
        "scavenger_hunt.asgi:application"
    ]
    
    # Execute the command
    subprocess.run(cmd) 