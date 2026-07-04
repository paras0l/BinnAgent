"""merge parser and prompt execution heads

Revision ID: j0e1f2a3b4c5
Revises: 1a2b3c4d5e6f, i9d0e1f2a3b4
Create Date: 2026-07-04 18:00:00.000000

"""

from typing import Sequence, Union

revision: str = "j0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = (
    "1a2b3c4d5e6f",
    "i9d0e1f2a3b4",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
