"""extend reading workshop generation

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-07-09 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, Sequence[str], None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reading_material_histories",
        sa.Column("curriculum_node_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "reading_material_histories",
        sa.Column("material_type", sa.String(length=30), nullable=False, server_default="passage"),
    )
    op.add_column(
        "reading_material_histories",
        sa.Column("generation_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_reading_material_histories_curriculum_node_id",
        "reading_material_histories",
        ["curriculum_node_id"],
    )
    op.create_foreign_key(
        "fk_reading_material_histories_curriculum_node_id",
        "reading_material_histories",
        "curriculum_nodes",
        ["curriculum_node_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_reading_material_histories_curriculum_node_id",
        "reading_material_histories",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_reading_material_histories_curriculum_node_id",
        table_name="reading_material_histories",
    )
    op.drop_column("reading_material_histories", "generation_context")
    op.drop_column("reading_material_histories", "material_type")
    op.drop_column("reading_material_histories", "curriculum_node_id")
