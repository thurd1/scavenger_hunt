#!/bin/bash
# Simple script to run Daphne with the proper parameters

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "env" ]; then
    source env/bin/activate
fi

# Collect static files first
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run Daphne with the proper host and port
echo "Starting Daphne server..."
python -m daphne -b 0.0.0.0 -p 8000 scavenger_hunt.asgi:application 