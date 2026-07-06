"""Add pg_trgm extension and GIN trigram indexes backing global search.

app/api/search.py does leading-wildcard ILIKE ('%term%') against these
columns, which cannot use a plain B-tree index. A GIN trigram index lets
Postgres accelerate these instead of falling back to a sequential scan.

Revision ID: 20260702_14
Revises: 20260702_13
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260702_14"
down_revision = "20260702_13"
branch_labels = None
depends_on = None

_INDEXES = [
    ("ix_customers_name_trgm", "customers", "name"),
    ("ix_customers_email_trgm", "customers", "email"),
    ("ix_customers_company_trgm", "customers", "company"),
    ("ix_products_name_trgm", "products", "name"),
    ("ix_products_sku_trgm", "products", "sku"),
    ("ix_invoices_invoice_number_trgm", "invoices", "invoice_number"),
    ("ix_tasks_title_trgm", "tasks", "title"),
    ("ix_tasks_description_trgm", "tasks", "description"),
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for index_name, table, column in _INDEXES:
        op.execute(
            f"CREATE INDEX {index_name} ON {table} USING gin ({column} gin_trgm_ops)"
        )


def downgrade() -> None:
    for index_name, _table, _column in reversed(_INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
    # Leave the pg_trgm extension installed on downgrade - dropping it would
    # break any other index/query relying on it, and CREATE EXTENSION is idempotent.
