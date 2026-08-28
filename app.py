#!/usr/bin/env python3
"""
🏛️ Sympose: Zero-Bloat Multi-Model AI Agent Hub
Main Entry Point
"""

import sys
import os
import argparse
from sympose.config import ConfigManager
from sympose.profiles import ProfileManager
from sympose.engine import PersonaEngine
from sympose.cli import TerminalInterface
from sympose.slack import MultiAgentSlackRunner


def main():
    parser = argparse.ArgumentParser(description="Sympose Multi-Model Agent Hub")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s 0.2.6")
    parser.add_argument("--cli", action="store_true", help="Launch interactive Terminal CLI Hub")
    parser.add_argument("--persona", type=str, default=None, help="Initial persona handle (e.g. samantha)")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to master config YAML file")
    parser.add_argument("--slack", action="store_true", help="Launch Slack Socket Mode Daemon")
    parser.add_argument("--dashboard", "--web", action="store_true", help="Launch Web Dashboard & Standalone Vault Explorer")
    parser.add_argument("--setup", "--onboard", action="store_true", help="Launch interactive setup & onboarding wizard")
    args = parser.parse_args()

    from sympose.bootstrap import resolve_workspace_dir, ensure_workspace, run_first_run_onboarding
    from dotenv import load_dotenv

    workspace_dir = resolve_workspace_dir()
    is_fresh = ensure_workspace(workspace_dir)
    load_dotenv(os.path.join(workspace_dir, ".env"))

    # Run onboarding wizard if requested (--setup) or if fresh workspace
    if (args.setup or is_fresh) and not args.dashboard and not args.slack:
        run_first_run_onboarding(workspace_dir, force=args.setup)

    # Initialize configuration & profile managers
    config_path = args.config if os.path.isabs(args.config) or os.path.exists(args.config) else os.path.join(workspace_dir, args.config)
    config = ConfigManager(config_path)
    
    profiles_dir = config.get("runtime.profiles_dir", "profiles")
    if not os.path.isabs(profiles_dir) and not os.path.exists(profiles_dir):
        profiles_dir = os.path.join(workspace_dir, profiles_dir)

    pm = ProfileManager(profiles_dir=profiles_dir)
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
