"""add learner email account selection and invitation relationships

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-07-10 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, Sequence[str], None] = "p6q7r8s9t0u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("learners_email_key", "learners", type_="unique")
    op.execute(
        """
        UPDATE learners
        SET email = CASE
            WHEN btrim(email) = '' THEN NULL
            ELSE lower(btrim(email))
        END
        WHERE email IS NOT NULL
        """
    )
    op.create_index("ix_learners_email", "learners", ["email"])

    op.add_column("learners", sa.Column("invite_code", sa.String(length=32), nullable=True))
    op.add_column(
        "learners",
        sa.Column(
            "invited_by_learner_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.execute(
        """
        DO $$
        DECLARE
            learner_row RECORD;
            candidate TEXT;
            attempt INTEGER;
        BEGIN
            FOR learner_row IN SELECT id FROM learners ORDER BY created_at, id LOOP
                attempt := 0;
                LOOP
                    candidate := 'BINN-' || upper(
                        substr(md5(learner_row.id::text || ':' || attempt::text), 1, 10)
                    );
                    EXIT WHEN NOT EXISTS (
                        SELECT 1 FROM learners WHERE invite_code = candidate
                    );
                    attempt := attempt + 1;
                END LOOP;
                UPDATE learners SET invite_code = candidate WHERE id = learner_row.id;
            END LOOP;
        END $$
        """
    )
    op.alter_column("learners", "invite_code", existing_type=sa.String(length=32), nullable=False)
    op.create_unique_constraint("uq_learners_invite_code", "learners", ["invite_code"])
    op.create_index(
        "ix_learners_invited_by_learner_id",
        "learners",
        ["invited_by_learner_id"],
    )
    op.create_foreign_key(
        "fk_learners_invited_by_learner_id",
        "learners",
        "learners",
        ["invited_by_learner_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_learners_invited_by_learner_id", "learners", type_="foreignkey")
    op.drop_index("ix_learners_invited_by_learner_id", table_name="learners")
    op.drop_constraint("uq_learners_invite_code", "learners", type_="unique")
    op.drop_column("learners", "invited_by_learner_id")
    op.drop_column("learners", "invite_code")
    op.drop_index("ix_learners_email", table_name="learners")
    op.execute(
        """
        WITH duplicate_emails AS (
            SELECT id, row_number() OVER (PARTITION BY email ORDER BY created_at, id) AS ordinal
            FROM learners
            WHERE email IS NOT NULL
        )
        UPDATE learners
        SET email = NULL
        FROM duplicate_emails
        WHERE learners.id = duplicate_emails.id AND duplicate_emails.ordinal > 1
        """
    )
    op.create_unique_constraint("learners_email_key", "learners", ["email"])
