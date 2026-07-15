"""Best-effort email discovery from a business's own public website.

Not a data-enrichment API - just reads the business's own homepage (and,
failing that, an obvious "contact" page) the same way any web crawler
would, looking for a published email address. No guarantee of finding
one; many small-business sites only offer a contact form.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx

from app.utils.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT = 5.0
_USER_AGENT = "BiznizFlowPilot-LeadGen/1.0 (+https://mmnexus.co.za)"

_MAILTO_RE = re.compile(r'mailto:([^"\'?\s]+)', re.IGNORECASE)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_CONTACT_LINK_RE = re.compile(
    r'href=["\']([^"\']*contact[^"\']*)["\']', re.IGNORECASE
)

# Common false-positive sources picked up from template/tracking boilerplate,
# not the business's own address.
_JUNK_DOMAINS = {
    "sentry.io", "wixpress.com", "godaddy.com", "cloudflare.com",
    "google-analytics.com", "gstatic.com", "schema.org", "w3.org",
    "example.com", "mailchimp.com", "wordpress.com", "wordpress.org",
}


def _registrable_domain(url: str) -> str:
    host = httpx.URL(url).host or ""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _extract_email(html: str, site_domain: str) -> str | None:
    candidates = [m.group(1) for m in _MAILTO_RE.finditer(html)] + _EMAIL_RE.findall(html)
    seen: list[str] = []
    for raw in candidates:
        email = raw.strip().rstrip(".,;").lower()
        if "@" not in email or email in seen:
            continue
        domain = email.rsplit("@", 1)[-1]
        if domain in _JUNK_DOMAINS or domain.endswith(".png") or domain.endswith(".jpg"):
            continue
        seen.append(email)
        if domain == site_domain or domain.endswith(f".{site_domain}"):
            return email  # same-domain match - highest confidence, return immediately

    return seen[0] if seen else None


def find_email(website_url: str) -> str | None:
    """Try to find a published email on a business's website. Never raises -
    any failure (timeout, non-HTML, connection error) just yields None."""
    try:
        headers = {"User-Agent": _USER_AGENT}
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=headers) as client:
            home = client.get(website_url)
            if home.status_code != 200 or "text/html" not in home.headers.get("content-type", ""):
                return None

            site_domain = _registrable_domain(str(home.url))
            email = _extract_email(home.text, site_domain)
            if email:
                return email

            contact_match = _CONTACT_LINK_RE.search(home.text)
            if not contact_match:
                return None

            contact_url = urljoin(str(home.url), contact_match.group(1))
            contact_page = client.get(contact_url)
            if contact_page.status_code != 200:
                return None
            return _extract_email(contact_page.text, site_domain)
    except (httpx.HTTPError, ValueError) as e:
        logger.info("Email scrape failed for %s: %s", website_url, e)
        return None
