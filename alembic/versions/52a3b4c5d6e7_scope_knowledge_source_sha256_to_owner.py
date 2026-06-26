"""scope knowledge source sha256 to owner

Revision ID: 52a3b4c5d6e7
Revises: 41a2b3c4d5e6
Create Date: 2026-06-26 15:10:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "52a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "41a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("knowledge_sources_sha256_key", "knowledge_sources", type_="unique")
    op.create_unique_constraint(
        "uq_knowledge_sources_owner_sha256",
        "knowledge_sources",
        ["owner_learner_id", "sha256"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_knowledge_sources_owner_sha256",
        "knowledge_sources",
        type_="unique",
    )
    op.create_unique_constraint("knowledge_sources_sha256_key", "knowledge_sources", ["sha256"])
