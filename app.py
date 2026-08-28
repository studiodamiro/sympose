#!/usr/bin/env python3
"""
🏛️ Sympose: Zero-Bloat Multi-Model AI Agent Hub
Main Entry Point
"""

import sys
import argparse
from sympose.config import ConfigManager
from sympose.profiles import ProfileManager
from sympose.engine import PersonaEngine
from sympose.cli import TerminalInterface
from sympose.slack import MultiAgentSlackRunner


def main():
    parser = argparse.ArgumentParser(description="Sympose Multi-Model Agent Hub")
    parser.add_argument("--cli", action="store_true", help="Launch interactive Terminal CLI Hub")
    parser.add_argument("--persona", type=str, default=None, help="Initial persona handle (samantha, grace, aurelius)")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to master config YAML file")
    parser.add_argument("--slack", action="store_true", help="Launch Slack Socket Mode Daemon")
    parser.add_argument("--dashboard", "--web", action="store_true", help="Launch Web Dashboard & Standalone Vault Explorer")
    args = parser.parse_args()

    # Initialize configuration & profile managers
    config = ConfigManager(args.config)
    pm = ProfileManager(profiles_dir=config.get("runtime.profiles_dir", "profiles"))
    engine = PersonaEngine(pm)

    default_persona = args.persona or config.get("runtime.default_persona", "samantha")

    if args.dashboard:
        from sympose.server import run_server
        run_server(engine, host="0.0.0.0", port=8000)
    elif args.slack:
        MultiAgentSlackRunner.run_all(engine, persona_override=args.persona)
    else:
        cli = TerminalInterface(engine)
        cli.run(initial_handle=default_persona)


if __name__ == "__main__":
    main()
