#!/usr/bin/env python
"""One-off: layer the expanded ~75-person sample dataset onto an existing
trial business, on top of whatever demo data it already has.

seed_sample_data() is purely additive (every call just inserts new rows
scoped to the given business_id) - it was written for brand-new signups,
but nothing about it assumes the business is empty, so calling it again
against an existing account is safe to run. It does mean some things get
duplicated alongside what's already there (e.g. a second "Operations"
department, a second "Naledi Khumalo" colleague account) rather than
replacing the old small dataset - that's the explicit tradeoff of running
this instead of a destructive wipe-and-reseed.

Usage:
    python scripts/reseed_trial_business.py --email owner@example.com
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.models.hr import Department, Employee  # noqa: E402
from app.repositories.user import UserRepository  # noqa: E402
from app.services.trial_seed import seed_sample_data  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Layer the expanded sample dataset onto an existing business.")
    parser.add_argument("--email", required=True, help="Email of the account owner whose business to re-seed.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = UserRepository(db).get_by_email_all(args.email)
        if not user:
            print(f"No user found with email {args.email!r}.", file=sys.stderr)
            sys.exit(1)

        before_depts = db.query(Department).filter(Department.business_id == user.business_id).count()
        before_emps = db.query(Employee).filter(Employee.business_id == user.business_id).count()

        print(f"Target: {user.email} (user_id={user.id}, business_id={user.business_id})")
        print(f"Before: {before_depts} departments, {before_emps} employees.")
        confirm = input("Add the expanded sample dataset to this business? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)

        seed_sample_data(db, business_id=user.business_id, owner_user_id=user.id)
        db.commit()

        after_depts = db.query(Department).filter(Department.business_id == user.business_id).count()
        after_emps = db.query(Employee).filter(Employee.business_id == user.business_id).count()
        print(f"After: {after_depts} departments, {after_emps} employees.")
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
