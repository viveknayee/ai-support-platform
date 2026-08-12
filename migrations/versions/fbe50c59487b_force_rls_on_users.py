"""force_rls_on_users

Revision ID: fbe50c59487b
Revises: 4330d52b4676
Create Date: 2026-08-10 14:16:40.426828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbe50c59487b'
down_revision: Union[str, Sequence[str], None] = '4330d52b4676'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY;")