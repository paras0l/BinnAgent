"""extend grammar profiles for the licensed EGP catalog

Revision ID: b8c9d0e1f2a4
Revises: a7b8c9d0e1f3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a4"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("grammar_can_do_profiles", sa.Column("external_id", sa.Integer(), nullable=True))
    op.add_column("grammar_can_do_profiles", sa.Column("guideword", sa.Text(), nullable=True))
    op.add_column("grammar_can_do_profiles", sa.Column("lexical_range", sa.Text(), nullable=True))
    op.add_column("grammar_can_do_profiles", sa.Column("source_url", sa.String(500), nullable=True))
    op.add_column("grammar_can_do_profiles", sa.Column("source_attribution", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_grammar_can_do_profiles_external_id",
        "grammar_can_do_profiles",
        ["external_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_grammar_can_do_profiles_external_id",
        "grammar_can_do_profiles",
        type_="unique",
    )
    for column in ("source_attribution", "source_url", "lexical_range", "guideword", "external_id"):
        op.drop_column("grammar_can_do_profiles", column)
