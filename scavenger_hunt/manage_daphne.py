#!/usr/bin/env python
import os
import sys
import subprocess

# Configuration
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 8001       # Use port 8001 as requested

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
        "-b", HOST,    # Bind to all interfaces
        "-p", str(PORT),  # Use port 8001
        "scavenger_hunt.asgi:application"
    ]
    
    print(f"Starting Daphne on {HOST}:{PORT}")
    
    # Execute the command
    subprocess.run(cmd) 