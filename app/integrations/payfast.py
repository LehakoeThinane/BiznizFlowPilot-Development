"""PayFast integration - signature generation and ITN (webhook) validation.

No official PayFast SDK exists for Python; this implements their documented
protocol directly with stdlib + httpx (already a dependency).

Checkout itself isn't an API call the way Stripe's Checkout Session is - it's
a signed redirect to PayFast's own hosted payment page (see
app/services/billing.py::create_checkout_session). This module only covers
the two pieces that are genuinely PayFast-specific: signing, and validating
the ITN PayFast posts back once payment completes.
"""

from __future__ import annotations

import hashlib
import socket
from urllib.parse import quote_plus

import httpx

from app.core.config import settings

# PayFast migrated their Payment API to AWS in July 2025 - IPs are no longer
# static, so ITN source-IP validation resolves these hostnames at request
# time rather than checking against a hardcoded range (per PayFast's own
# current guidance).
_ITN_SOURCE_HOSTNAMES = [
    "www.payfast.co.za",
    "api.payfast.co.za",
    "ips.payfast.co.za",
    "w1w.payfast.co.za",
    "w2w.payfast.co.za",
]


def payfast_host() -> str:
    return "sandbox.payfast.co.za" if settings.payfast_sandbox else "www.payfast.co.za"


def build_signature(ordered_fields: dict[str, str], passphrase: str) -> str:
    """MD5 signature over `ordered_fields` in the order given - PayFast requires
    the exact order fields were sent (outgoing) or received (ITN), never
    alphabetical. Blank values are excluded, matching PayFast's own reference
    implementation.
    """
    parts = [f"{key}={quote_plus(str(value))}" for key, value in ordered_fields.items() if str(value).strip()]
    payfast_string = "&".join(parts)
    if passphrase:
        payfast_string += f"&passphrase={quote_plus(passphrase)}"
    return hashlib.md5(payfast_string.encode()).hexdigest()


def validate_source_ip(client_ip: str) -> bool:
    """Confirm `client_ip` currently resolves to one of PayFast's ITN hostnames."""
    hostnames = list(_ITN_SOURCE_HOSTNAMES)
    if settings.payfast_sandbox:
        hostnames.append("sandbox.payfast.co.za")

    valid_ips: set[str] = set()
    for hostname in hostnames:
        try:
            _, _, addresses = socket.gethostbyname_ex(hostname)
            valid_ips.update(addresses)
        except OSError:
            continue  # a single hostname failing to resolve shouldn't block the others
    return client_ip in valid_ips


def confirm_with_payfast(raw_body: bytes) -> bool:
    """PayFast's own recommended ITN check: POST the raw ITN body back to them
    and require the literal response "VALID"."""
    try:
        response = httpx.post(
            f"https://{payfast_host()}/eng/query/validate",
            content=raw_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    except httpx.HTTPError:
        return False
    return response.text.strip() == "VALID"
