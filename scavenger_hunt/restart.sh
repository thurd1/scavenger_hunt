#!/bin/bash
# Restart script for the scavenger hunt application

echo "Activating virtual environment..."
source env/bin/activate

echo "Installing/updating requirements..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Daphne server..."
python manage_daphne.py 