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
import datetime
import logging
from typing import Optional, Tuple

log = logging.getLogger(__name__)


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
