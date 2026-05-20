"""merge subscription and memory migration heads

Revision ID: f7a8b9c0d1e2
Revises: a0b1c2d3e4f5, f6a7b8c9d0e1
Create Date: 2026-05-20
"""

from typing import Sequence, Union


revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = ('a0b1c2d3e4f5', 'f6a7b8c9d0e1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
