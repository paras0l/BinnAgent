"""add email verification challenges

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-07-10 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "r8s9t0u1v2w3"
down_revision: Union[str, Sequence[str], None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_verification_challenges",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("code_salt", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_verification_challenges_email",
        "email_verification_challenges",
        ["email"],
    )
    op.create_index(
        "ix_email_verification_challenges_sent_at",
        "email_verification_challenges",
        ["sent_at"],
    )
    op.create_index(
        "ix_email_verification_challenges_expires_at",
        "email_verification_challenges",
        ["expires_at"],
    )
    op.create_index(
        "ix_email_verification_challenges_email_sent",
        "email_verification_challenges",
        ["email", "sent_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_verification_challenges_email_sent",
        table_name="email_verification_challenges",
    )
    op.drop_index(
        "ix_email_verification_challenges_expires_at",
        table_name="email_verification_challenges",
    )
    op.drop_index(
        "ix_email_verification_challenges_sent_at",
        table_name="email_verification_challenges",
    )
    op.drop_index(
        "ix_email_verification_challenges_email",
        table_name="email_verification_challenges",
    )
    op.drop_table("email_verification_challenges")
