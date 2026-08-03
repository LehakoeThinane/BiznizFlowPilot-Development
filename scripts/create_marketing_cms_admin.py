#!/usr/bin/env python
"""Bootstrap the first marketing CMS (blog admin) account.

Marketing CMS admins have no self-registration endpoint - the first one
must be created here, directly against the DB.

Usage:
    python scripts/create_marketing_cms_admin.py --email you@mmnexus.co.za --full-name "Your Name"
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.services.marketing_cms_auth import MarketingCmsAuthService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a marketing CMS admin account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        service = MarketingCmsAuthService(db)
        admin = service.create_admin(email=args.email, password=password, full_name=args.full_name)
        print(f"Created marketing CMS admin: {admin.email} (id={admin.id})")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
