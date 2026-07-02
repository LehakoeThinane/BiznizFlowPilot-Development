"""
Alembic script template for generating migration files.
"""

from alembic import op
import sqlalchemy as sa
${imports}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade database schema."""
    ${upgrades}


def downgrade() -> None:
    """Downgrade database schema."""
    ${downgrades}
