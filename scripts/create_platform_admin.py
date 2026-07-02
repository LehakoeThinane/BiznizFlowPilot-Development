#!/usr/bin/env python
"""Bootstrap the first platform admin account.

Platform admins have no self-registration endpoint (unlike tenant users) -
the first one must be created here, directly against the DB. Subsequent
admins can be created by an existing admin/super_admin via
POST /platform/v1/admins.

Usage:
    python scripts/create_platform_admin.py --email you@vendor.com --role super_admin
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.services.platform_auth import PlatformAuthService  # noqa: E402

VALID_ROLES = ("support", "billing_ops", "admin", "super_admin")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a platform admin account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--role", choices=VALID_ROLES, default="super_admin")
    parser.add_argument("--impersonation-allowed", action="store_true")
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
        service = PlatformAuthService(db)
        admin = service.create_admin(
            email=args.email,
            password=password,
            full_name=args.full_name,
            platform_role=args.role,
            impersonation_allowed=args.impersonation_allowed,
            created_by_id=None,
        )
        print(f"Created platform admin: {admin.email} (role={admin.platform_role}, id={admin.id})")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
