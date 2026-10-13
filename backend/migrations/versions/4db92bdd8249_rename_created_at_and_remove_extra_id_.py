"""rename created_at and remove extra id index

Revision ID: 4db92bdd8249
Revises: 89ff437f5eb7
Create Date: 2026-10-12 14:15:09.903814

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4db92bdd8249"
down_revision: Union[str, Sequence[str], None] = "89ff437f5eb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "users",
        "createdAt",
        new_column_name="created_at",
    )
    op.drop_index("ix_users_id", table_name="users")
    pass


def downgrade() -> None:
    """Downgrade schema."""
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.alter_column(
        "users",
        "created_at",
        new_column_name="createdAt",
    )
    pass
