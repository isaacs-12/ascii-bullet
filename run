#!/bin/bash
# Run the ASCII Bullet Hell game

# Activate virtual environment and run the game
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo "Starting ASCII Bullet Hell..."
python main.py

