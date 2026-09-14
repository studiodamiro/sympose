#!/usr/bin/env python3
"""
🏛️ Sympose: Zero-Bloat Multi-Model AI Persona Hub
Main Entry Point
"""

import argparse
import os

from sympose.cli import TerminalInterface
from sympose.config import ConfigManager
from sympose.engine import PersonaEngine
from sympose.profiles import ProfileManager
from sympose.slack import MultiPersonaSlackRunner


def main():
    parser = argparse.ArgumentParser(description="Sympose Multi-Model Persona Hub")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s 0.2.26")
    parser.add_argument(
        "--cli", action="store_true", help="Launch interactive Terminal CLI Hub"
    )
    parser.add_argument(
        "--persona",
        type=str,
        default=None,
        help="Initial persona handle (e.g. samantha)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to master config YAML file",
    )
    parser.add_argument(
        "--slack", action="store_true", help="Launch Slack Socket Mode Daemon"
    )
    parser.add_argument(
        "--dashboard",
        "--web",
        action="store_true",
        help="Launch Web Dashboard & Standalone Vault Explorer",
    )
    parser.add_argument(
        "--setup",
        "--onboard",
        action="store_true",
        help="Launch interactive setup & onboarding wizard",
    )
    parser.add_argument(
        "--sync-skills",
        action="store_true",
        help="Sync packaged prompts/skills into the workspace, prompting "
        "before overwriting anything that differs (run after an upgrade)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="With --sync-skills, overwrite differing files without prompting",
    )
    args = parser.parse_args()

    from dotenv import load_dotenv

    from sympose.bootstrap import (
        ensure_workspace,
        resolve_workspace_dir,
        run_first_run_onboarding,
        sync_builtin_content,
    )

    workspace_dir = resolve_workspace_dir()
    is_fresh = ensure_workspace(workspace_dir)
    # sympose.config already loaded this same file at import time (before
    # DEFAULT_MODEL was resolved); this is a redundant, explicit no-op.
    load_dotenv(os.path.join(workspace_dir, ".env"))

    if args.sync_skills:
        report = sync_builtin_content(workspace_dir, auto_yes=args.yes)
        print("\n".join(report) if report else "Already up to date.")
        return

    # Run onboarding wizard if requested (--setup) or if fresh workspace
    if (args.setup or is_fresh) and not args.dashboard and not args.slack:
        run_first_run_onboarding(workspace_dir, force=args.setup)

    # Initialize configuration & profile managers
    config_path = (
        args.config
        if os.path.isabs(args.config)
        else os.path.join(workspace_dir, args.config)
    )
    config = ConfigManager(config_path)

    profiles_dir = config.get("runtime.profiles_dir", "profiles")
    if not os.path.isabs(profiles_dir):
        profiles_dir = os.path.join(workspace_dir, profiles_dir)

    pm = ProfileManager(profiles_dir=profiles_dir)
    engine = PersonaEngine(pm)

    default_persona = args.persona or config.get("runtime.default_persona", "samantha")

    if args.dashboard:
        from sympose.server import run_server
        from sympose.tls import ensure_dashboard_tls_choice

        # Defaults to localhost-only; set SYMPOSE_DASHBOARD_HOST=0.0.0.0 to opt into
        # LAN exposure explicitly. Every route requires the ADR-064.1 dashboard
        # password (auto-generated into .env on first boot if unset). HTTPS vs
        # plain HTTP (ADR-064.2) is asked once on first interactive boot and
        # persisted to .env from then on — see `ensure_dashboard_tls_choice`.
        tls_enabled = ensure_dashboard_tls_choice(workspace_dir)
        run_server(
            engine,
            workspace_dir=workspace_dir,
            host=os.getenv("SYMPOSE_DASHBOARD_HOST", "127.0.0.1"),
            port=8000,
            tls=tls_enabled,
        )
    elif args.slack:
        MultiPersonaSlackRunner.run_all(
            engine, persona_override=args.persona, workspace_dir=workspace_dir
        )
    else:
        cli = TerminalInterface(engine)
        cli.run(initial_handle=default_persona)


if __name__ == "__main__":
    main()
