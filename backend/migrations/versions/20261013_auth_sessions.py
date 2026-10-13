"""Add revocable sessions and user permissions.

Revision ID: 20261013_auth_sessions
Revises: 1243f607c185
"""

import sqlalchemy as sa
from alembic import op

revision = "20261013_auth_sessions"
down_revision = "1243f607c185"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("refresh_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_user_tokens_user_id", "user_tokens", ["user_id"])
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("permission", sa.String(16), server_default="user", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", name="uq_user_permissions_user_id"),
        sa.CheckConstraint(
            "permission IN ('user', 'admin')", name="ck_user_permissions_permission"
        ),
    )
    op.execute("INSERT INTO user_permissions (user_id) SELECT id FROM users")


def downgrade() -> None:
    op.drop_table("user_permissions")
    op.drop_index("ix_user_tokens_user_id", table_name="user_tokens")
    op.drop_table("user_tokens")
