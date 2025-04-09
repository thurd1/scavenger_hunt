#!/bin/bash
# Script to run Django development server with Channels support

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "env" ]; then
    source env/bin/activate
fi

# Collect static files first
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run Django development server
echo "Starting Django development server..."
python manage.py runserver 0.0.0.0:8000 