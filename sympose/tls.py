"""
Zero-dependency self-signed TLS for the dashboard (ADR-064.2).

Certs are generated in-process with `cryptography` — no external `openssl`/
`mkcert` binary, no OS trust-store mutation — and cached under the workspace
so boot after the first is free. Browsers show a one-time "not secure,
proceed" warning per device for the self-signed root, an accepted trade-off
for a single-user personal-LAN threat model (see ADR-064's Alternatives
rejected). If `cryptography` isn't installed, TLS is silently skipped and the
dashboard falls back to plain HTTP rather than failing to boot.
"""

import os
import sys
import datetime
import logging
from typing import Optional, Tuple

log = logging.getLogger(__name__)


def ensure_dashboard_tls_choice(workspace_dir: str) -> bool:
    """Returns whether the dashboard should serve over HTTPS, asking once on
    first `--dashboard` boot and persisting the answer to the workspace .env —
    the same generate-once-and-persist pattern as `ensure_dashboard_password`.

    If `SYMPOSE_DASHBOARD_TLS` is already set (env or a prior boot's .env),
    that value wins and no prompt happens. A non-interactive launch (no TTY —
    a background service, a script) also skips the prompt and keeps today's
    default (HTTPS), since there's no one there to answer it.
    """
    raw = os.getenv("SYMPOSE_DASHBOARD_TLS")
    if raw is not None:
        return raw.strip().lower() not in ("0", "false", "no")

    if not sys.stdin.isatty():
        return True

    try:
        from rich.prompt import Confirm
    except ImportError:
        return True

    use_tls = Confirm.ask(
        "\n[bold cyan]Serve the dashboard over HTTPS?[/bold cyan] "
        "[dim]Self-signed — your browser will warn once per device. The "
        "dashboard binds to 127.0.0.1 only, so plain HTTP is equally private "
        "here; HTTPS just avoids that warning at the cost of it.[/dim]",
        default=True,
    )
    os.environ["SYMPOSE_DASHBOARD_TLS"] = "1" if use_tls else "0"
    env_file = os.path.join(workspace_dir, ".env")
    try:
        with open(env_file, "a", encoding="utf-8") as f:
            f.write(f"\nSYMPOSE_DASHBOARD_TLS={'1' if use_tls else '0'}\n")
    except Exception:
        log.warning(
            "[tls] Could not persist the HTTPS choice to %s (will ask again next boot).",
            env_file,
        )
    return use_tls


def ensure_self_signed_cert(workspace_dir: str) -> Optional[Tuple[str, str]]:
    """Returns (certfile, keyfile) paths, generating them on first boot if missing.
    Returns None if the `cryptography` package isn't available."""
    cert_dir = os.path.join(workspace_dir, ".certs")
    certfile = os.path.join(cert_dir, "dashboard.crt")
    keyfile = os.path.join(cert_dir, "dashboard.key")
    if os.path.isfile(certfile) and os.path.isfile(keyfile):
        return certfile, keyfile

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        import ipaddress
    except ImportError:
        log.warning(
            "[tls] `cryptography` not installed; dashboard will serve over plain "
            "HTTP. Run `pip install cryptography` to enable self-signed HTTPS (ADR-064.2)."
        )
        return None

    try:
        os.makedirs(cert_dir, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sympose.local")])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("sympose.local"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        with open(certfile, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        with open(keyfile, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        try:
            os.chmod(keyfile, 0o600)
        except Exception:
            pass
        log.info("[tls] Generated self-signed dashboard certificate in %s", cert_dir)
        return certfile, keyfile
    except Exception:
        log.warning("[tls] Failed to generate self-signed certificate; falling back to plain HTTP.", exc_info=True)
        return None
