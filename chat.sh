#!/usr/bin/env bash
# ==============================================================================
# 🏛️ Sympose Quick Launcher
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
    echo "⚡ Launching Sympose Slack Socket Mode Daemon..."
    python3 app.py --slack
else
    python3 app.py --cli "$@"
fi
