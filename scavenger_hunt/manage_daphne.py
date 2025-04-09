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
    
    # Print settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scavenger_hunt.settings')
    print(f"Settings module: {os.environ['DJANGO_SETTINGS_MODULE']}")
    
    # Use subprocess to run Daphne with the correct ASGI application
    daphne_cmd = [
        sys.executable, "-m", "daphne",
        "-p", str(PORT),
        "-b", HOST,
        "scavenger_hunt.asgi:application"
    ]
    
    # Execute Daphne as a separate process
    subprocess.run(daphne_cmd) 