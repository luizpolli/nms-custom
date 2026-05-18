"""service target score

Revision ID: 0007_service_target_score
Revises: 0006_service_score_history
Create Date: 2026-05-18 12:55:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_service_target_score"
down_revision: Union[str, None] = "0006_service_score_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("services", sa.Column("target_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("services", "target_score")
