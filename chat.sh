#!/usr/bin/env bash
# ==============================================================================
# sympose // quick launcher
# Usage: ./chat.sh [--slack | --persona grace | --persona aurelius]
# ==============================================================================

set -e

# Resolve project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if present
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Route arguments
if [ "$1" == "--slack" ]; then
    echo "Starting Sympose Slack Socket Mode Daemon..."
    python3 app.py --slack
elif [ "$1" == "--dashboard" ] || [ "$1" == "--web" ]; then
    echo "Starting Sympose Dashboard & Vault Gateway..."
    python3 app.py --dashboard
else
    python3 app.py --cli "$@"
fi

