#!/bin/bash

echo "Seeding database..."

# make sure we're in the backend directory
cd "$(dirname "$0")/../backend" || exit 1

# check venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "venv is not activated. Activating..."
    source ..backend/venv/bin/activate
fi

# run seed script
python -m scripts.seed

if [ $? -eq 0 ]; then
    echo "Seed completed successfully"
else
    echo "Seed failed"
    exit 1
fi