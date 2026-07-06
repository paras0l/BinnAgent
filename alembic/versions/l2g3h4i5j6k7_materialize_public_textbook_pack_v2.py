"""materialize public textbook pack v2

Revision ID: l2g3h4i5j6k7
Revises: k1f2a3b4c5d6
Create Date: 2026-07-06 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from src.knowledge.public_textbook_seed import materialize_public_textbook_seed, stable_seed_uuid

revision: str = "l2g3h4i5j6k7"
down_revision: Union[str, Sequence[str], None] = "k1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCE_STABLE_IDS = ("pep-grade7-upper-2024", "pep-grade7-lower-2024")


def upgrade() -> None:
    materialize_public_textbook_seed(op.get_bind())


def downgrade() -> None:
    source_ids = [stable_seed_uuid("source", stable_id) for stable_id in SOURCE_STABLE_IDS]
    op.execute(
        sa.text(
            """
            DELETE FROM knowledge_sources
            WHERE id = ANY(CAST(:source_ids AS uuid[]))
            """
        ).bindparams(source_ids=[str(source_id) for source_id in source_ids])
    )
