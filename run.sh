#!/usr/bin/env bash
# Run ASCII Bullet Hell, creating a virtualenv on first launch.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --quiet -r requirements.txt
fi

exec ./venv/bin/python main.py "$@"
