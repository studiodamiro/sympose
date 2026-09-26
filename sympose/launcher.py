"""The `sympose` command (docs/decisions/028): `sympose cli` for the terminal chat and `sympose web`
for the web app, the API and the built app together in one process."""

import argparse
import os
import sys


_OWN_NAMES = ["127.0.0.1", "localhost"]


def _run_cli(args: argparse.Namespace) -> int:
    from sympose.cli.__main__ import main as run_cli

    run_cli()
    return 0


def _run_web(args: argparse.Namespace) -> int:
    from sympose.envfile import load_env

    load_env()
    import uvicorn

    from starlette.middleware.trustedhost import TrustedHostMiddleware

    from sympose import web_static
    from sympose.server import create_app

    try:
        port = args.port if args.port is not None else int(os.getenv("PORT", "8000"))
    except ValueError:
        print(f"sympose web: PORT must be a number, not {os.getenv('PORT')!r}", file=sys.stderr)
        return 1
    app = create_app()
    try:
        web_static.mount_web_app(app)
    except web_static.WebAppMissing as e:
        print(f"sympose web: {e}", file=sys.stderr)
        return 1
    # Only this machine's own names may address it: a hostile page cannot reach the vault API by
    # pointing its own domain name at 127.0.0.1 (DNS rebinding), since its Host header would differ.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_OWN_NAMES)
    print(f"Sympose web app: http://127.0.0.1:{port}  (Ctrl-C to stop)")
    uvicorn.run(app, host="127.0.0.1", port=port)  # this machine only: no auth, no TLS
    return 0


def _run_doctor(args: argparse.Namespace) -> int:
    from sympose import doctor
    from sympose.envfile import load_env

    load_env()
    return doctor.run(fix=args.fix)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sympose", description="Sympose: an AI companion for your Obsidian vault.")
    commands = parser.add_subparsers(dest="command", title="commands")
    cli = commands.add_parser("cli", help="chat with a persona in the terminal")
    cli.set_defaults(run=_run_cli)
    web = commands.add_parser("web", help="open the web app for your vault (on this machine only)")
    web.add_argument("--port", type=int, help="the port to listen on (default: PORT in .env, else 8000)")
    web.set_defaults(run=_run_web)
    doctor = commands.add_parser("doctor", help="check the installation and, with --fix, correct what is Sympose's own")
    doctor.add_argument("--fix", action="store_true", help="apply the fixes (persona folder names, wrong-kind settings)")
    doctor.set_defaults(run=_run_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
